"""Validate exported figures against saved metrics and check PDF bounds/vector output."""
from pathlib import Path
import json,math,zipfile,shutil,hashlib
from collections import defaultdict
import numpy as np
import pymupdf as fitz
from analyze import DEST,ROOT,CONDS
OUT=ROOT/'findings/medcase24-figures'

def main():
 d=json.loads((OUT/'figure-data.json').read_text());s=json.loads((DEST/'summary.json').read_text());a=json.loads((OUT/'audit.json').read_text());clock=json.loads((OUT/'token-clock.json').read_text())
 assert len(a['pdfs'])==22
 assert a['pdfs']['00_all_figures.pdf']==19 and a['pdfs']['03_facts_by_output_tokens.pdf']==1
 assert a['master_order'][:3]==['01_uptake_prime.pdf','02_output_preference.pdf','08_new_fact_preference.pdf']
 pages=0;outside=[];images=0
 for name,n in a['pdfs'].items():
  doc=fitz.open(OUT/name);assert len(doc)==n
  for i,p in enumerate(doc):
   assert p.get_text().strip();images+=len(p.get_images());pages+=1
   for word in p.get_text('words'):
    x0,y0,x1,y1=word[:4]
    if x0<-.5 or y0<-.5 or x1>p.rect.width+.5 or y1>p.rect.height+.5:outside.append((name,i,word))
 assert not outside,outside[:5]
 assert images==0,images
 for key,metric in [('01_uptake_prime','uptake_prime'),('output_own','output_own'),('output_prime','output_prime')]:
  points=d[key]['points'];assert len(points)==1080
  groups=defaultdict(list)
  for p in points:groups[(p['condition'],p['round'])].append(p)
  assert all(len(v)==72 for v in groups.values())
  for r in d[key]['summary']:
   if r['field']=='all':continue
   old=next(x for x in s['profiles'] if all(x[k]==r[k] for k in ['condition','round','field']) and x['unit']=='equivalence' and x['scheme']=='fractional' and x['match']=='equivalence')['metrics'][metric]
   assert (r['mean'] is None and old['mean'] is None) or abs(r['mean']-old['mean'])<1e-12
 for rd in [2,3]:
  rows=d[f'flow-R{rd}']
  for r in rows:
   if r['condition']!='average':continue
   vs=[x['mean'] for x in rows if x['condition']!='average' and x['source']==r['source'] and x['target']==r['target'] and x['mean'] is not None]
   assert abs(r['mean']-np.mean(vs))<1e-12
 r=json.loads((OUT/'revision-analysis.json').read_text())
 from analyze_figure_revision import case_values,paired_test
 for kind in ['correctness','majority']:
  for row in d[f'{kind}-pooled-boxplot']:
   es=[e for e in r['pooled_edges'] if e['final']==row['final'] and (e['seat']==e['target'])==(row['receiver']=='self') and (kind=='correctness' or e['panel_kind']=='two_one') and e['truth' if kind=='correctness' else 'status']==row['group']]
   cv=case_values(es);assert cv==row['case_values'] and len(cv)<=24
   assert abs(np.mean(list(cv.values()))-row['stat']['mean'])<1e-12
 for test in r['pooled_tests']:
  assert test['effect']['n']<=24
  if test['p'] is not None:assert 0<=test['p']<=test['q']<=1
  es=[e for e in r['pooled_edges'] if e['final']==test['final'] and (e['seat']==e['target'])==(test['receiver']=='self') and (test['kind']=='correctness' or e['panel_kind']=='two_one')]
  key='truth' if test['kind']=='correctness' else 'status'
  fresh=paired_test(es,key,'Correct' if key=='truth' else 'Minority','Incorrect' if key=='truth' else 'Majority')
  assert fresh['case_gaps']==test['case_gaps'] and fresh['p']==test['p']
 for row in r['repetition_cases']:
  assert row['sum_round_facts']-row['trace_facts']==row['repeat_excess']+row['bridge_reduction']
  clockrow=next(c for c in clock['runs'] if c['case']==row['case'] and c['condition']==row['condition'] and c['round']==0)
  assert clockrow['trajectory'][-1][1]==row['trace_facts']
 lookup={(x['case'],x['condition'],x['round'],x['seat'],x['scope']):x for x in r['novel_profiles']}
 for key,x in lookup.items():
  if x['scope']!='all':continue
  a=lookup[key[:-1]+('new_outputs',)];b=lookup[key[:-1]+('old_outputs',)]
  assert a['facts']+b['facts']==x['facts']
  if x['round']==1:assert a['facts']==x['facts']
 for receiver in ['self','peers']:
  rs=d[f'factorial-pooled-{receiver}'];assert len(rs)==24
  for x in rs:
   if x['condition']=='average':
    vs=[z['mean'] for z in rs if z['condition']!='average' and z['truth']==x['truth'] and z['status']==x['status'] and z['mean'] is not None]
    assert x['settings']==len(vs) and abs(x['mean']-np.mean(vs))<1e-12
 for c in CONDS:
  mean=next(x for x in d['token-R-1'] if x['condition']==c)
  rounds=[next(x for x in d[f'token-R{rd}'] if x['condition']==c) for rd in [1,2,3]]
  assert all(x['tokens']==mean['tokens'] and x['cases']==mean['cases'] for x in rounds)
  expected=np.mean([x['case_curves'] for x in rounds],axis=0)
  assert np.allclose(expected,mean['case_curves']) and np.allclose(expected.mean(axis=0),mean['mean'])
  for row in rounds:
   for cid,curve in zip(row['cases'],row['case_curves']):
    old=next(x for x in clock['runs'] if x['case']==cid and x['condition']==c and x['round']==row['round'])
    ar=np.asarray(old['trajectory']);assert np.array_equal(ar[np.searchsorted(ar[:,0],row['tokens'],side='right')-1,1],curve)
 for kind in ['correctness','majority']:
  rows=d[f'{kind}-pooled-scatter']
  for receiver in ['self','peers']:
   assert [x['final'] for x in rows if x['receiver']==receiver]==['Correct','Correct','Incorrect','Incorrect']
  assert {x['panel'] for x in d[f'{kind}-pooled-boxplot']}=={'All','Correct','Incorrect'}
 for r in clock['runs']:
  pos=[x[0] for x in r['trajectory']];assert pos==sorted(pos) and pos[-1]==r['tokens']
  for q in r['trajectory']:assert 0<=q[1]<=q[2]
  assert all(0<=e[0]<=r['tokens'] for e in r['events'])
 result={'passed':True,'pdf_files':22,'pages_including_duplicate_exports':pages,'master_pages':19,'embedded_raster_images':images,'out_of_page_text':len(outside),'trace_round_token_curves':len(clock['runs']),'token_endpoint_checks':480,'api_calls':0}
 (OUT/'verification.json').write_text(json.dumps(result,indent=2))
 shutil.copyfile(ROOT/'docs/medcase24-figures.md',OUT/'README.md')
 files=sorted(p for p in OUT.iterdir() if p.suffix in ['.pdf','.json','.md'] and p.name!='checksums.json')
 (OUT/'checksums.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
 with zipfile.ZipFile(OUT/'medcase24-figures.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in files+[OUT/'checksums.json']:z.write(p,p.name)
  z.write(ROOT/'scripts/study_report/export_figures.py','code/export_figures.py')
  z.write(ROOT/'scripts/study_report/check_figures.py','code/check_figures.py')
  for name in ['analyze_figure_revision.py','pooled_figures.py']:z.write(ROOT/'scripts/study_report'/name,'code/'+name)
 print(json.dumps(result))
if __name__=='__main__':main()
