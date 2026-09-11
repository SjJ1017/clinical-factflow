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
 assert len(a['pdfs'])==20
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
 for kind,key,plus,minus in [('correctness','associations','Correct','Incorrect'),('majority','majority','Minority','Majority')]:
  for rd in [1,2]:
   rows=d[f'{kind}-R{rd}-paired']
   for receiver in ['self','peers']:
    for outcome in ['all','correct','wrong']:
     rs={r['group']:r for r in rows if r['outcome']==outcome and r['receiver']==receiver}
     old=next(r for r in s['social_uptake'][key] if r['unit']=='equivalence' and r['match']=='equivalence' and r['scope']=='all' and r['grading']=='inclusive' and r['condition']=='all' and r['round']==rd and r['outcome']==outcome and r['measure']==receiver and (key!='majority' or r['composition']=='all'))
     if old['gap']['mean'] is None:assert rs[plus]['stat']['mean'] is None or rs[minus]['stat']['mean'] is None
     else:assert abs(rs[plus]['stat']['mean']-rs[minus]['stat']['mean']-old['gap']['mean'])<1e-12
 for r in clock['runs']:
  pos=[x[0] for x in r['trajectory']];assert pos==sorted(pos) and pos[-1]==r['tokens']
  for q in r['trajectory']:assert 0<=q[1]<=q[2]
  assert all(0<=e[0]<=r['tokens'] for e in r['events'])
 # Correct-minority cells exist; this is not the same as correct minority vs two D majority.
 for rd,n in [(1,3),(2,2)]:
  r=next(r for r in d[f'factorial-R{rd}-all'] if r['receiver']=='self' and r['status']=='minority' and r['correctness']=='correct');assert r['n']==n
 result={'passed':True,'pdf_files':20,'pages_including_duplicate_exports':pages,'master_pages':27,'embedded_raster_images':images,'out_of_page_text':len(outside),'trace_round_token_curves':len(clock['runs']),'token_endpoint_checks':480,'api_calls':0}
 (OUT/'verification.json').write_text(json.dumps(result,indent=2))
 shutil.copyfile(ROOT/'docs/medcase24-figures.md',OUT/'README.md')
 files=sorted(p for p in OUT.iterdir() if p.suffix in ['.pdf','.json','.md'] and p.name!='checksums.json')
 (OUT/'checksums.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
 with zipfile.ZipFile(OUT/'medcase24-figures.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in files+[OUT/'checksums.json']:z.write(p,p.name)
  z.write(ROOT/'scripts/study_report/export_figures.py','code/export_figures.py')
  z.write(ROOT/'scripts/study_report/check_figures.py','code/check_figures.py')
 print(json.dumps(result))
if __name__=='__main__':main()
