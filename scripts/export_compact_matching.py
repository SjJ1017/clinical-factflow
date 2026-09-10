#!/usr/bin/env python3
"""Lossless numeric export: one atoms JSON.gz and one relations NPZ. No model work."""
from pathlib import Path
import argparse,sqlite3,json,gzip,zipfile,hashlib,os,fcntl
import numpy as np

def j(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def array(z,name,a):
    with z.open(name+'.npy','w',force_zip64=True) as f:np.lib.format.write_array(f,a,allow_pickle=False)
def export(root,out):
    out.mkdir(exist_ok=True,parents=True)
    if any((out/name).exists() for name in ['atoms.json.gz','relations.npz','checksums.json']):
        raise FileExistsError('Use a fresh export directory; completed snapshots are immutable.')
    locks=[]
    for gpu in [0,1]:
        shard=root/f'medcase24-pairs-gpu{gpu}'
        index=json.loads((shard/'index.json').read_text())
        assert index['complete'] and index['input_complete'] and len(index['cases'])==12
        lock=(shard/'matching.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(lock)
    atomcases=[];meta={'version':'compact-pairs-v1','complete':False,'relation_codes':{'0':'UNRELATED','1':'A_ENTAILS_B','2':'B_ENTAILS_A','3':'EQUIVALENT'},'stage_codes':{'0':'blocker','1':'nli'},'layout':'case_00/field.npy ...; aligned rows in lexicographic local (a,b) order; global atom integer IDs; JSON metadata encoded as uint8; no pickle','float_precision':'float64 unchanged from SQLite; NaN means no NLI score on blocker negatives','cases':[]};offset=0
    dtype=np.dtype([(n,t) for n,t in [('a','u4'),('b','u4'),('cosine','f8'),('lexical','f8'),('token_intersection','u4'),('a_token_count','u4'),('b_token_count','u4'),('combined','f8'),('rank_a','u4'),('rank_b','u4'),('relation','u1'),('stage','u1'),('reason','u1'),('judgment_id','i4'),('forced','u1'),('ab_margin','f8'),('ba_margin','f8')]])
    reasons={};codes={'UNRELATED':0,'A_ENTAILS_B':1,'B_ENTAILS_A':2,'EQUIVALENT':3}
    with zipfile.ZipFile(out/'relations.partial.npz','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for gpu in [0,1]:
            for f in sorted((root/f'medcase24-pairs-gpu{gpu}').glob('*.sqlite')):
                db=sqlite3.connect(f'file:{f}?mode=ro',uri=True);db.row_factory=sqlite3.Row
                assert db.execute('select name from policies').fetchall()[0][0]=='initial' and db.execute('select count(*) from policies').fetchone()[0]==1
                metadata={r['key']:json.loads(r['value']) for r in db.execute('select key,value from metadata')};cid=metadata['case_id'];nodes=[dict(r) for r in db.execute('select idx,node_id,logic_text,payload from nodes order by idx')];n=len(nodes);total=n*(n-1)//2
                prefix=f'case_{len(atomcases):02d}';a=np.zeros(total,dtype=dtype);a['ab_margin']=a['ba_margin']=np.nan;a['judgment_id']=-1;lookup={}
                # No expensive 20-million-row text join: map hashes transiently, discard after export.
                for r in db.execute('select * from pairs'):
                    x,y=r['a'],r['b'];i=x*(2*n-x-1)//2+y-x-1;lookup[r['pair_id']]=i
                    for name in ['a','b','cosine','lexical','token_intersection','a_token_count','b_token_count','combined','rank_a','rank_b']:a[name][i]=r[name]
                assert len(lookup)==total
                judgments=[]
                for r in db.execute('select * from judgments'):
                    d=dict(r);i=lookup[d['pair_id']];a['ab_margin'][i]=d['ab_margin'];a['ba_margin'][i]=d['ba_margin'];d['payload']=json.loads(d['payload']);d['row']=i;judgments.append(d)
                annotated=0;counts={}
                for r in db.execute("select * from annotations where policy='initial'"):
                    assert r['status']=='complete';i=lookup[r['pair_id']];reason=r['reason'];reasons.setdefault(reason,len(reasons));a['relation'][i]=codes[r['relation']];a['stage'][i]=int(r['decision_stage']=='nli');a['reason'][i]=reasons[reason];a['judgment_id'][i]=r['judgment_id'] if r['judgment_id'] is not None else -1;a['forced'][i]=r['forced'];annotated+=1;counts[r['relation']]=counts.get(r['relation'],0)+1
                assert annotated==total
                scored=a['stage']==1;assert int(scored.sum())==len(judgments);assert np.isfinite(a['ab_margin'][scored]).all() and np.isfinite(a['ba_margin'][scored]).all()
                predicted=(a['ab_margin'][scored]>=5.28).astype('u1')+2*(a['ba_margin'][scored]>=5.28).astype('u1');assert np.array_equal(predicted,a['relation'][scored]);assert (a['relation'][~scored]==0).all()
                a['a']+=offset;a['b']+=offset
                for name in a.dtype.names:array(z,prefix+'/'+name,a[name].copy())
                array(z,prefix+'/judgments_json',np.frombuffer(j(judgments).encode(),dtype='u1'))
                extra={'metadata':metadata,'policies':[dict(r) for r in db.execute('select * from policies')],'attempts':[dict(r) for r in db.execute('select * from attempts')]}
                array(z,prefix+'/audit_json',np.frombuffer(j(extra).encode(),dtype='u1'))
                atomcases.append({'case_id':cid,'prefix':prefix,'nodes':[{'id':offset+r['idx'],'node_id':r['node_id'],'logic_text':r['logic_text'],'data':json.loads(r['payload'])} for r in nodes]})
                meta['cases'].append({'case_id':cid,'prefix':prefix,'gpu':gpu,'atom_offset':offset,'nodes':n,'pairs':total,'judgments':len(judgments),'counts':counts,'source_sqlite':str(f.relative_to(root))});offset+=n;db.close();print(j(meta['cases'][-1]),flush=True)
        meta['complete']=True;meta['reason_codes']={str(v):k for k,v in reasons.items()};assert len(atomcases)==24
        array(z,'metadata_json',np.frombuffer(j(meta).encode(),dtype='u1'))
    with gzip.open(out/'atoms.partial.json.gz','wt',encoding='utf-8',compresslevel=6) as stream:stream.write(j({'version':'compact-atoms-v1','complete':True,'cases':atomcases}))
    os.replace(out/'relations.partial.npz',out/'relations.npz');os.replace(out/'atoms.partial.json.gz',out/'atoms.json.gz')
    check={name:{'bytes':(out/name).stat().st_size,'sha256':hashlib.file_digest((out/name).open('rb'),'sha256').hexdigest()} for name in ['atoms.json.gz','relations.npz']}
    (out/'checksums.json').write_text(json.dumps(check,indent=2));print(j(check),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('out',type=Path);args=p.parse_args();export(args.root,args.out)
