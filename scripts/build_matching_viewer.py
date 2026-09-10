#!/usr/bin/env python3
"""Offline, auditable report from finished pair ledgers and immutable trace snapshots."""
from pathlib import Path
from collections import defaultdict, Counter
import argparse, json, math, hashlib, gzip
import numpy as np

THRESHOLDS=[4.0,4.5,4.78,5.0,5.28,5.5,5.78,6.0,6.5]
CONDITIONS=['shared-generic','shared-specialist','split-generic','split-specialist','split-mismatched']

def read(p): return json.loads(p.read_text())
def label(ab,ba,t): return (int(ab>=t) + 2*int(ba>=t))
def groups(ids,scores,t=5.28):
    eq={}
    for a,b,x,y in scores:
        if x>=t and y>=t: eq.setdefault(a,set()).add(b);eq.setdefault(b,set()).add(a)
    result=[]
    for i in sorted(ids):
        for g in result:
            if all(j in eq.get(i,set()) for j in g): g.append(i);break
        else: result.append([i])
    return len(result)

def stats(ids,scores,mentions):
    ids=set(ids); pairs=[s for s in scores if s[0] in ids and s[1] in ids]
    a=np.asarray(pairs,dtype=float).reshape((-1,4));base=(a[:,2]>=5.28).astype(int)+2*(a[:,3]>=5.28)
    rows=[]
    for t in THRESHOLDS:
        v=(a[:,2]>=t).astype(int)+2*(a[:,3]>=t)
        rows.append({'threshold':t,'equivalent':int((v==3).sum()),'one_way':int(((v==1)|(v==2)).sum()),'changed':int((v!=base).sum()),'transitions':dict(Counter(f'{int(x)}>{int(y)}' for x,y in zip(base,v) if x!=y))})
    return {'atoms':len(ids),'mentions':mentions,'all_pairs':len(ids)*(len(ids)-1)//2,'nli_pairs':len(pairs),'complete_link_groups':groups(ids,pairs),'thresholds':rows}

def mean_stats(items):
    out={k:sum(x[k] for x in items)/len(items) for k in ['atoms','mentions','all_pairs','nli_pairs','complete_link_groups']}
    out['traces']=len(items);out['thresholds']=[]
    for i,t in enumerate(THRESHOLDS):
        d={'threshold':t,**{k:sum(x['thresholds'][i][k] for x in items)/len(items) for k in ['equivalent','one_way','changed']}}
        trans=Counter()
        for x in items:trans.update(x['thresholds'][i]['transitions'])
        d['transitions_total']=dict(trans);out['thresholds'].append(d)
    return out

def load_scores(path):
    if path.suffix!='.npz': return read(path)
    # All IDs in NPZ are global integers; viewer IDs are local to a case.
    with np.load(path,allow_pickle=False) as z, gzip.open(path.with_name('atoms.json.gz'),'rt',encoding='utf-8') as f:
        atomstore=json.load(f);meta=json.loads(z['metadata_json'].tobytes())
        assert atomstore['complete'] and meta['complete']
        atoms={c['case_id']:c for c in atomstore['cases']};cases=[]
        for c in meta['cases']:
            p=c['prefix']+'/';mask=z[p+'stage']==1
            aa=z[p+'a'][mask].astype('int64')-c['atom_offset'];bb=z[p+'b'][mask].astype('int64')-c['atom_offset']
            ab=z[p+'ab_margin'][mask];ba=z[p+'ba_margin'][mask];rels=z[p+'relation'][mask]
            count=Counter(int(v) for v in rels);names={0:'UNRELATED',1:'A_ENTAILS_B',2:'B_ENTAILS_A',3:'EQUIVALENT'}
            audit=json.loads(z[p+'audit_json'].tobytes());policy=audit['policies'][0]
            cases.append({'case_id':c['case_id'],'node_ids':[n['node_id'] for n in atoms[c['case_id']]['nodes']],
              'scores':[[int(a),int(b),float(x),float(y)] for a,b,x,y in zip(aa,bb,ab,ba)],'total_pairs':c['pairs'],
              'groups':[['nli',names[k],'complete',v] for k,v in count.items()],
              'policy':[policy[k] for k in ['name','blocker_threshold','top_k','nli_threshold']]})
    return {'complete':True,'cases':cases}

def build(root,compact,out):
    bundle=root/'exports/medcase24-atoms';manifest=read(bundle/'manifest.json');sc=load_scores(compact)
    assert sc['complete'] and len(sc['cases'])==24
    scorecases={c['case_id']:c for c in sc['cases']}
    rawruns={}
    for p in sorted((root/'runs/medcase24-approved-20260909/traces').iterdir()):
        if not (p/'trace.json').exists():continue
        tr=read(p/'trace.json');mf=read(p/'manifest.json')
        if tr['status']!='complete':continue
        cid=next(iter(tr['cases'])); cfg=mf['config'];cond=next(c for c in CONDITIONS if cfg['name'].endswith(c))
        rawruns[p.name]=(cid,cond,tr['cases'][cid],cfg,read(p/'cases.json')[0],read(p/'references.private.json')[cid])
    assert len(rawruns)==120
    assert len({(v[0],v[1]) for v in rawruns.values()})==120
    runs=[];audit={'span_errors':[],'traces':0,'turns':0,'wire_same_round_violations':0,'unlocated_mentions':0}
    for entry in manifest['cases']:
        case=read(bundle/entry['file']);scase=scorecases[entry['case_id']];nodes=case['nodes'];assert [n['id'] for n in nodes]==scase['node_ids']
        assert scase['policy'][1:]==[.62,12,5.28]
        scores=scase['scores'];assert all(math.isfinite(v) for s in scores for v in s[2:])
        # Reproduce saved labels before doing sensitivity analysis.
        counter=Counter({0:0,1:0,2:0,3:0})
        counter.update(label(x,y,5.28) for _,_,x,y in scores)
        stored={g[1]:g[3] for g in scase['groups'] if g[0]=='nli'}
        for k,name in [(0,'UNRELATED'),(1,'A_ENTAILS_B'),(2,'B_ENTAILS_A'),(3,'EQUIVALENT')]:assert counter[k]==stored.get(name,0),(case['case_id'],counter,stored)
        for rid,(cid,cond,tr,cfg,source,ref) in rawruns.items():
            if cid!=case['case_id']:continue
            cards={};agents=cfg['agents'];assert len(agents)==3
            assert len({a['initial_context'] for a in agents})==1
            cards['metadata']={'id':'metadata','title':'Common patient metadata','text':agents[0]['initial_context'],'channel':'initial','facts':[],'visible':[]}
            for e in source['evidence']:
                cards[e['id']]={'id':e['id'],'title':e['id'],'domain':e['category'],'text':e['text'],'channel':'source','facts':[],'visible':[]}
            for t in tr['turns']:
                d=t['delivery'];visible=d['source_ids']+d['self_turn_ids']+d['peer_turn_ids']+(['metadata'] if d.get('initial_context_id') else [])
                for prev in d['peer_turn_ids']:
                    assert int(prev.split('|')[1])<t['round']
                cards[t['id']]={'id':t['id'],'title':f"{t['agent_id']} · Round {t['round']}",'agent':t['agent_id'],'round':t['round'],'text':t['output_text'],'diagnosis':t.get('final_diagnosis'),'channel':'output','facts':[],'visible':visible,'peers':d['peer_turn_ids'],'self':d['self_turn_ids']}
            atoms={};seen=set();output_ids=set();outputmentions=0
            for ni,n in enumerate(nodes):
                for m in n['mentions']:
                    for b in m['bindings']:
                        if Path(b['run_dir']).name!=rid:continue
                        p=b['provenance'];key='metadata' if p['channel']=='initial' else p.get('turn_id',p.get('source_id'))
                        unique=(key,m['task_id'],m['mention']['id'])
                        if unique in seen:continue
                        seen.add(unique);c=cards[key];mention=m['mention'];spans=[]
                        for occ in mention['occurrences']:
                            for lo,hi in occ['spans']:
                                assert 0<=lo<hi<=len(c['text']),(rid,key,lo,hi)
                                if c['text'][lo:hi]!=occ['quote']:audit['span_errors'].append([rid,key,mention['id']])
                                spans.append([len(c['text'][:lo].encode('utf-16-le'))//2,len(c['text'][:hi].encode('utf-16-le'))//2])
                        spans=sorted(set(map(tuple,spans)))
                        c['facts'].append({'id':ni,'spans':spans,'annotation':mention['annotation'],'quote':mention['quote']})
                        if not spans:audit['unlocated_mentions']+=1
                        atoms[ni]=[n['text'],n['qualifiers']]
                        if c['channel']=='output':output_ids.add(ni);outputmentions+=1
            local_scores=[s for s in scores if s[0] in atoms and s[1] in atoms]
            for c in cards.values():
                if c['channel']!='output':c['readers']=sorted({o['agent'] for o in cards.values() if o['channel']=='output' and c['id'] in o['visible']})
            run={'id':rid,'case':cid,'condition':cond,'question':source['question'],'agents':agents,'cards':list(cards.values()),'atoms':atoms,'scores':local_scores,'reference':ref['final_diagnosis'],'outcomes':tr['round_outcomes'],'metrics':{'output':stats(output_ids,local_scores,outputmentions),'all':stats(atoms,local_scores,len(seen))}}
            runs.append(run);audit['traces']+=1;audit['turns']+=len(tr['turns'])
    runs.sort(key=lambda r:(r['case'],CONDITIONS.index(r['condition'])))
    assert len(runs)==120 and audit['turns']==1080 and not audit['span_errors'],audit
    summary={'baseline':5.28,'thresholds':THRESHOLDS,'scopes':{s:mean_stats([r['metrics'][s] for r in runs]) for s in ['output','all']},'conditions':{c:{s:mean_stats([r['metrics'][s] for r in runs if r['condition']==c]) for s in ['output','all']} for c in CONDITIONS},'case_pool':{'nodes':sum(len(c['node_ids']) for c in sc['cases']),'all_pairs':sum(c['total_pairs'] for c in sc['cases']),'nli_pairs':sum(len(c['scores']) for c in sc['cases'])},'audit':audit,'provenance':{'compact_scores_sha256':hashlib.sha256(compact.read_bytes()).hexdigest(),'atom_manifest_sha256':hashlib.sha256((bundle/'manifest.json').read_bytes()).hexdigest(),'unit':'Distinct exact text + qualifier nodes per trace; unordered distinct-node pairs. Direct labels, no transitive closure.','sensitivity':'Fixed case-pooled blocker at 0.62/top12; reclassify both saved margins, no new inference.','complete_link':'Greedy complete-link in sorted node-ID order at 5.28; descriptive conservative grouping, not a gold fact count.'}}
    out.mkdir(parents=True,exist_ok=True)
    (out/'matching-summary.json').write_text(json.dumps(summary,indent=2))
    (out/'per-trace-metrics.json').write_text(json.dumps([{k:r[k] for k in ['id','case','condition','metrics']} for r in runs],indent=2))
    data=json.dumps({'runs':runs,'summary':summary,'conditions':CONDITIONS},ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    template=Path(__file__).with_name('matching-viewer-template.html').read_text()
    (out/'medcase24-trace-viewer.html').write_text(template.replace('__PAYLOAD__',data))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--scores',type=Path);p.add_argument('--out',type=Path)
    a=p.parse_args();build(a.root,a.scores or a.root/'runs/server-matching-20260910/compact/relations.npz',a.out or a.root/'findings')
