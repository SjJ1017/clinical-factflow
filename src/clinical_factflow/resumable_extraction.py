"""Version-locked extraction queue with per-request checkpoints and a hard stop."""
from __future__ import annotations
import argparse, fcntl, json, os, shlex, shutil, signal, threading, time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from pathlib import Path
import yaml
from .client import Client, json_object
from .config import Extraction, RunConfig, digest
from .extraction import extract_record, records_for
from .io import atomic_json, file_hash

class Paused(Exception):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def sealed_write(path, value):
    atomic_json(path, {'sha256': digest(value), 'value': value})

def sealed_read(path):
    obj = json.loads(Path(path).read_text())
    if digest(obj['value']) != obj['sha256']:
        raise ValueError(f'Checkpoint integrity failure: {path}')
    return obj['value']

class CheckpointClient:
    def __init__(self, settings, directory, allow_remote, stop, deadline, factory=Client):
        self.settings, self.directory = settings, Path(directory)
        self.allow_remote, self.stop, self.deadline, self.factory = allow_remote, stop, deadline, factory
        self.client = factory(settings.model_copy(update={'attempts':1}), self.directory / 'calls', allow_remote)

    def request(self, messages, response_model, sample_id, validate=None):
        key = digest([sample_id, messages, response_model.model_json_schema(), self.settings.model_dump()])
        path = self.directory / 'checkpoints' / (key + '.json')
        def decode(saved):
            value = response_model.model_validate(saved['value'])
            if validate: validate(value)
            return value, saved['info']
        if path.exists():
            return decode(sealed_read(path))
        # Recover a successful raw response if interrupted after its audit fsync
        # but before the checkpoint rename. Never reuse failed/truncated replies.
        sent = [dict(m) for m in messages]
        sent[0]['content'] += '\nReturn one JSON object matching this schema. No markdown.\n' + json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        for f in sorted((self.directory / 'calls').glob('*.json')):
            c = json.loads(f.read_text())
            if c.get('status') != 'ok' or c['sample_id'] != sample_id: continue
            req = c['request']
            same = (req.get('system') == '\n\n'.join(m['content'] for m in sent if m['role']=='system') and req['messages'] == [m for m in sent if m['role']!='system']) if self.settings.api_format=='anthropic' else req['messages']==sent
            if not same or req['model'] != self.settings.model: continue
            raw = c['response']
            content = ''.join(b['text'] for b in raw['content'] if b['type']=='text') if self.settings.api_format=='anthropic' else raw['choices'][0]['message']['content']
            saved = {'value':json_object(content), 'info':{'call_id':c['call_id'], 'usage':raw.get('usage'), 'response_model':raw.get('model'), 'system_fingerprint':raw.get('system_fingerprint'), 'raw_text':content, 'messages':sent, 'latency_seconds':c['wall_seconds']}}
            result = decode(saved); sealed_write(path, saved); return result
        last = None
        for _ in range(self.settings.attempts):
            remaining = self.deadline - time.time()
            if self.stop.is_set() or remaining < 5: raise Paused()
            settings = self.settings.model_copy(update={'attempts':1, 'timeout_seconds':min(self.settings.timeout_seconds, remaining-2)})
            self.client.settings = settings
            client = self.client
            try:
                value, info = client.request(messages, response_model, sample_id, validate=validate)
                sealed_write(path, {'value':value.model_dump(), 'info':info})
                return value, info
            except Exception as exc:
                last = exc
                if self.stop.is_set() or time.time() >= self.deadline-5: raise Paused() from exc
        raise RuntimeError(f'{sample_id}: attempts exhausted ({type(last).__name__})') from last

def build_tasks(study, project):
    status = json.loads((study/'status.json').read_text())
    if status['status'] != 'complete': raise ValueError('Generation study is incomplete')
    tasks, parents = {}, []
    for entry in status['runs']:
        p = (project/entry['run_dir']).resolve()
        manifest = json.loads((p/'manifest.json').read_text())
        if manifest['status'] != 'complete': raise ValueError('Failed generation run')
        cfg = RunConfig.model_validate(manifest['config'])
        if digest(manifest['config']) != manifest['config_hash']: raise ValueError('Frozen configuration hash mismatch')
        if not cfg.dataset.allow_remote_processing: raise ValueError('Dataset forbids remote extraction')
        for name,h in manifest['artifact_hashes'].items():
            if file_hash(p/name) != h: raise ValueError(f'Parent artifact changed: {p/name}')
        parents.append({'run_dir':entry['run_dir'],'manifest_hash':file_hash(p/'manifest.json'),'artifact_hashes':manifest['artifact_hashes'],'condition':entry['condition'],'case_id':entry['case_id']})
        cases=json.loads((p/'cases.json').read_text()); trace=json.loads((p/'trace.json').read_text())
        for rec in records_for(cfg,cases,trace):
            binding={'run_dir':entry['run_dir'],'record_id':rec['id'],'provenance':rec['provenance']}
            ch=rec['provenance']['channel']; cid=rec['provenance']['case_id']
            if ch=='output':
                rec={**rec,'id':manifest['run_id']+'/'+rec['id'],'provenance':{**rec['provenance'],'execution_id':manifest['run_id']}}
                identity=['output',entry['run_dir'],rec['id']]
            elif ch=='initial':
                rec={'id':cid+'/common-metadata/'+digest(rec['text'])[:16],'text':rec['text'],'provenance':{'case_id':cid,'channel':'initial','scope':'shared-metadata'}}
                identity=['initial',cid,rec['text']]
            else:
                identity=['source',cid,rec['provenance']['source_id'],rec['text']]
            key=digest(identity)
            if key in tasks:
                if tasks[key]['record'] != rec: raise ValueError('Non-identical reusable evidence')
                tasks[key]['bindings'].append(binding)
            else: tasks[key]={'id':key,'record':rec,'bindings':[binding]}
    return list(tasks.values()), parents

def source_hashes():
    root=Path(__file__).parent
    return {name:file_hash(root/name) for name in ['resumable_extraction.py','extraction.py','client.py','config.py','models.py','io.py']}

def execute(tasks,cfg,target,deadline,stop,client_factory=Client):
    done={}; failed={}; active={}; paused=[]
    for task in tasks:
        p=target/'results'/(task['id']+'.json')
        if p.exists():
            result=sealed_read(p)
            if result['task_hash'] != digest(task) or result['result']['record_hash'] != digest(task['record']): raise ValueError('Result/task mismatch')
            done[task['id']]=file_hash(p)
    pending=iter(t for t in tasks if t['id'] not in done)
    started=now(); exhausted=False; consecutive_failures=0
    def one(task):
        c=CheckpointClient(cfg.model,target/'tasks'/task['id'],True,stop,deadline,factory=client_factory)
        result=extract_record(c,cfg,task['record'])
        p=target/'results'/(task['id']+'.json');sealed_write(p,{'task_hash':digest(task),'result':result})
        return file_hash(p)
    def save(state):
        progress={'status':state,'started_at':started,'updated_at':now(),'stop_at':datetime.fromtimestamp(deadline,timezone.utc).isoformat(),'total':len(tasks),'completed':len(done),'failed_this_session':len(failed),'active':len(active),'pending':len(tasks)-len(done),'completed_hashes':done,'errors':failed}
        atomic_json(target/'status.json',progress)
        return progress
    pool=ThreadPoolExecutor(max_workers=cfg.max_parallel)
    try:
        last=0
        while True:
            if time.time()>=deadline-5:stop.set()
            while not stop.is_set() and not exhausted and len(active)<cfg.max_parallel:
                task=next(pending,None)
                if task is None:exhausted=True;break
                active[pool.submit(one,task)]=task
            if not active: break
            finished,_=wait(active,timeout=1,return_when=FIRST_COMPLETED)
            for f in finished:
                task=active.pop(f)
                try:
                    done[task['id']]=f.result();consecutive_failures=0
                except Paused:paused.append(task['id'])
                except Exception as exc:
                    consecutive_failures+=1
                    if consecutive_failures>=3:stop.set()
                    failed[task['id']]={'error_type':type(exc).__name__,'at':now()}
                    atomic_json(target/'errors'/(task['id']+'.json'),failed[task['id']])
            if time.time()-last>=30:
                s=save('pausing' if stop.is_set() else 'running');print(json.dumps({k:v for k,v in s.items() if k not in ['completed_hashes','errors']}),flush=True);last=time.time()
        state='complete' if len(done)==len(tasks) else 'paused' if stop.is_set() or paused else 'needs_attention'
        result=save(state);atomic_json(target/'sessions'/(started.replace(':','-')+'.json'),result)
        return result
    finally:
        pool.shutdown(wait=True,cancel_futures=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--study',required=True,type=Path);ap.add_argument('--config',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--minutes',type=float,default=30);ap.add_argument('--stop-at');args=ap.parse_args()
    if args.minutes<=0:raise ValueError('minutes must be positive')
    project=Path.cwd();target=args.out.resolve();target.mkdir(parents=True,exist_ok=True)
    lock=(target/'queue.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cfgdoc=yaml.safe_load(args.config.read_text());cfg=Extraction.model_validate(cfgdoc['extraction'])
    tasks,parents=build_tasks(args.study.resolve(),project)
    manifest={'version':'resumable-extraction-v1','config':cfgdoc,'tasks':tasks,'parents':parents,'source_hashes':source_hashes()}
    if (target/'manifest.json').exists():
        if sealed_read(target/'manifest.json') != manifest:raise ValueError('Frozen extraction manifest differs; restore saved config/code, do not mix versions')
    else:
        sealed_write(target/'manifest.json',manifest);shutil.copy2(args.config,target/'extraction-config.yaml')
        snap=target/'pipeline-source-snapshot';snap.mkdir()
        for p in Path(__file__).parent.glob('*.py'):shutil.copy2(p,snap/p.name)
    for line in (project/'.env').read_text().splitlines():
        name,sep,value=line.removeprefix('export ').partition('=')
        if sep and name.strip()==cfg.model.api_key_env:
            parts=shlex.split(value,comments=True)
            if len(parts)!=1:raise ValueError('Malformed configured key')
            os.environ[name.strip()]=parts[0]
    if not os.environ.get(cfg.model.api_key_env or ''):raise ValueError('Missing configured API key')
    deadline=time.time()+args.minutes*60
    if args.stop_at:
        limit=datetime.fromisoformat(args.stop_at)
        if limit.tzinfo is None:raise ValueError('stop-at must include timezone')
        deadline=min(deadline,limit.timestamp())
    if deadline<=time.time():raise ValueError('Stop time has passed')
    stop=threading.Event();finished=threading.Event()
    for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:stop.set())
    # Bound a hung socket/read as well as normal request timeouts. Each durable
    # success is sealed independently; a killed in-flight request is retried later.
    def hard_stop():
        if not finished.wait(max(0,deadline-time.time())):
            atomic_json(target/'hard-stop.json',{'at':now(),'reason':'requested deadline','resume':'Validate result and request checkpoint files; status counts may lag.'})
            try:
                s=json.loads((target/'status.json').read_text());s.update(status='paused',active=0,updated_at=now(),hard_stop=True);atomic_json(target/'status.json',s)
            finally:os._exit(0)
    threading.Thread(target=hard_stop,daemon=True).start()
    print(json.dumps({'event':'started','records':len(tasks),'parents':len(parents),'model':cfg.model.model,'workers':cfg.max_parallel,'stop_at':datetime.fromtimestamp(deadline,timezone.utc).isoformat()}),flush=True)
    try:
        result=execute(tasks,cfg,target,deadline,stop)
        print(json.dumps({k:v for k,v in result.items() if k not in ['completed_hashes','errors']}),flush=True)
    finally:finished.set()

if __name__=='__main__':main()
