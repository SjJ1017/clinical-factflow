"""Offline case-paired study metrics. No extraction changes and no model calls."""
from pathlib import Path
from collections import defaultdict,Counter
import json,math,hashlib,itertools,sys
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
from judge_names import ROOT,OUT,load_runs,norm,pid,pair
DEST=ROOT/'findings/medcase24-study'
FIELDS=['clinical','laboratory','imaging']
TAGS=['history','examination','laboratory','pathology','imaging','diagnosis','treatment','other']
MAP={'history':'clinical','examination':'clinical','laboratory':'laboratory','pathology':'laboratory','imaging':'imaging','diagnosis':'shared','treatment':'shared','other':'shared'}
CONDS=['shared-generic','shared-specialist','split-generic','split-specialist','split-mismatched']
ROLE={'Clinical assessment specialist':'clinical','Laboratory and pathology specialist':'laboratory','Imaging specialist':'imaging'}
METRICS=['output_own','output_other','output_prime','input_own','share_shift','uptake_own','uptake_other','uptake_prime','peer_excess']
RNG=np.random.default_rng(20260910)
BOOT=RNG.integers(0,24,size=(2000,24))

def finite(x):return x is not None and math.isfinite(x)
def avg(values):
 v=[x for x in values if finite(x)];return float(np.mean(v)) if v else None

def summarize(v):
 v=[x for x in v if finite(x)];n=len(v)
 if not n:return {'mean':None,'n':0,'lo':None,'hi':None}
 a=np.asarray(v);ix=BOOT if n==24 else np.random.default_rng(20260910+n).integers(0,n,size=(2000,n));bs=a[ix].mean(axis=1)
 return {'mean':float(a.mean()),'n':n,'lo':float(np.quantile(bs,.025)),'hi':float(np.quantile(bs,.975))}

def components(ids,edges):
 ids=set(ids);parent={x:x for x in ids}
 def find(x):
  while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
  return x
 for a,b in edges:
  if a in ids and b in ids:
   x,y=find(a),find(b)
   if x!=y:parent[max(x,y)]=min(x,y)
 groups=defaultdict(set)
 for x in ids:groups[find(x)].add(x)
 return list(groups.values())

def domain_sets(cards):
 labels=defaultdict(set)
 for c in cards:
  for f in c['facts']:labels[f['id']].update(f['annotation']['clinical_domain'])
 return labels

def units(cards,edges,unit):
 labels=domain_sets(cards);gs=components(labels,edges) if unit=='equivalence' else [{x} for x in labels]
 return [{'ids':g,'tags':set().union(*(labels[i] for i in g))} for g in gs]

def weights(tags,field,scheme):
 own=sum(MAP[t]==field for t in tags);other=sum(MAP[t] in FIELDS and MAP[t]!=field for t in tags)
 return (float(own>0),float(other>0)) if scheme=='inclusive' else (own/len(tags),other/len(tags))

def entropy(us,scheme):
 counts={t:0. for t in TAGS}
 for u in us:
  for t in u['tags']:counts[t]+=1 if scheme=='inclusive' else 1/len(u['tags'])
 total=sum(counts.values());p=[v/total for v in counts.values() if v>0] if total else []
 h=-sum(x*math.log2(x) for x in p)
 return {'entropy_bits':h,'entropy_normalized':h/3,'effective_types':2**h,'type_mass':counts,'distribution':{k:v/total if total else 0 for k,v in counts.items()}}

def retained(u,output_ids,adj):return any(x in output_ids or bool(adj.get(x,set())&output_ids) for x in u['ids'])
def uptake(us,out_ids,adj,field,scheme):
 own=other=own_hit=other_hit=0.
 for u in us:
  a,b=weights(u['tags'],field,scheme);hit=retained(u,out_ids,adj);own+=a;other+=b;own_hit+=a*hit;other_hit+=b*hit
 own_rate=own_hit/own if own else None;other_rate=other_hit/other if other else None
 return {'own_den':own,'other_den':other,'own_num':own_hit,'other_num':other_hit,'uptake_own':own_rate,'uptake_other':other_rate,'uptake_prime':own_rate-other_rate if own_rate is not None and other_rate is not None else None}

def main():
 DEST.mkdir(parents=True,exist_ok=True);runs=load_runs();judge=json.loads((OUT/'results.json').read_text());assert judge['complete'] and judge['thinking_blocks']==0 and judge['charged_or_reserved_usd']<.1
 review=json.loads((OUT/'review.json').read_text());assert review['complete'];labels=review['labels'];base={r['case']:{a['id']:ROLE[a['role']] for a in r['agents']} for r in runs if r['condition']=='split-specialist'}
 def judge_label(a,b):
  if not a:return 'abstain'
  if norm(a)==norm(b):return 'S'
  return labels[pid(a,b)]
 def accuracy(a,g):
  code=judge_label(a,g);return {'prediction':a,'reference':g,'exact':float(norm(a)==norm(g)) if a else 0.,'fuzzy_same':float(code=='S'),'fuzzy_inclusive':float(code in ['S','L']),'fuzzy_upper':float(code in ['S','L','U']),'label':code,'uncertain':int(code=='U'),'abstain':int(not a)}
 profiles=[];graphs=[];counts=[];acc=[];mapping=[];caseinventory=[];domain_disagreement=0;component_diagnostics=[]
 for r in runs:
  cond=r['condition'];cid=r['case'];byid={c['id']:c for c in r['cards']};outs=[c for c in r['cards'] if c['channel']=='output'];initial=[c for c in r['cards'] if c['channel']!='output'];alloutput=set(f['id'] for c in outs for f in c['facts']);initialids=set(f['id'] for c in initial for f in c['facts'])
  fields={a['id']:ROLE.get(a['role'],base[cid][a['id']]) for a in r['agents']};assert sorted(fields.values())==sorted(FIELDS)
  if cond=='split-mismatched':assert all(fields[a]!=base[cid][a] for a in fields)
  mapping.append({'case':cid,'condition':cond,'role_by_seat':fields,'information_by_seat':{a:sorted({c['domain'] for c in initial if c['channel']=='source' and a in c['readers']}) for a in fields},'virtual_roles':cond=='shared-generic'})
  eq=[];related=[];eqadj=defaultdict(set);entadj=defaultdict(set)
  for a,b,x,y in r['scores']:
   if x>=5.28:entadj[a].add(b)
   if y>=5.28:entadj[b].add(a)
   if x>=5.28 or y>=5.28:related.append((a,b))
   if x>=5.28 and y>=5.28:eq.append((a,b));eqadj[a].add(b);eqadj[b].add(a)
  egs=components(alloutput,eq);wgs=components(alloutput,related)
  component_diagnostics.append({'case':cid,'condition':cond,'atoms':len(alloutput),'equivalence_groups':len(egs),'entailment_groups':len(wgs),'largest_equivalence_share':max(map(len,egs))/len(alloutput),'largest_entailment_share':max(map(len,wgs))/len(alloutput)})
  for mode,edges in [('equivalence',eq),('entailment',related)]:
   counts.append({'case':cid,'condition':cond,'scope':'trace','round':0,'mode':mode,'facts':len(components(alloutput,edges)),'atoms':len(alloutput)})
   counts.append({'case':cid,'condition':cond,'scope':'trace_all','round':-1,'mode':mode,'facts':len(components(alloutput|initialids,edges)),'atoms':len(alloutput|initialids)})
   previous=set()
   for rd in [1,2,3]:
    current=[c for c in outs if c['round']==rd];ids=set(f['id'] for c in current for f in c['facts']);prefix=previous|ids
    new_output=sum(bool(g&ids) and not bool(g&previous) for g in components(prefix,edges))
    old=previous|initialids;new_initial=sum(bool(g&ids) and not bool(g&old) for g in components(old|ids,edges))
    us=units(current,edges,'equivalence')
    counts.append({'case':cid,'condition':cond,'scope':'round','round':rd,'mode':mode,'facts':len(us),'atoms':len(ids),'new_vs_outputs':new_output,'new_vs_initial':new_initial,'cumulative_facts':len(components(prefix,edges)),**{scheme:entropy(us,scheme) for scheme in ['inclusive','fractional']}})
    previous|=ids
  for c in outs:
   rd=c['round'];agent=c['agent'];field=fields[agent];acc.append({'case':cid,'condition':cond,'round':rd,'level':'agent','field':field,'seat':agent,**accuracy(c['diagnosis'],r['reference'])})
   inputs=[byid[i] for i in c['visible']];out_ids={f['id'] for f in c['facts']}
   for unit in ['equivalence','atoms']:
    ous=units([c],eq,unit);ius=units(inputs,eq,unit)
    for scheme in ['inclusive','fractional']:
     peer_sets=[units([pc],eq,unit) for pc in outs if pc['round']==rd and pc['agent']!=agent]
     peer_field=avg([sum(weights(u['tags'],field,scheme)[0] for u in ps)/len(ps) for ps in peer_sets])
     own=sum(weights(u['tags'],field,scheme)[0] for u in ous)/len(ous);other=sum(weights(u['tags'],field,scheme)[1] for u in ous)/len(ous)
     inp=sum(weights(u['tags'],field,scheme)[0] for u in ius)/len(ius)
     for match,adj in [('equivalence',eqadj),('entailment',entadj)]:
      up=uptake(ius,out_ids,adj,field,scheme)
      row={'case':cid,'condition':cond,'round':rd,'seat':agent,'field':field,'unit':unit,'scheme':scheme,'match':match,'output_facts':len(ous),'input_facts':len(ius),'output_own':own,'output_other':other,'output_prime':own-other,'peer_excess':own-peer_field,'input_own':inp,'share_shift':own-inp,**up};profiles.append(row)
      if rd>1:
       for source in r['agents']:
        sid=source['id'];sourceid=f'{sid}|{rd-1}';assert sourceid in c['visible'];sus=units([byid[sourceid]],eq,unit)
        graphs.append({'case':cid,'condition':cond,'round':rd,'from':fields[sid],'to':field,'self':sid==agent,'source_seat':sid,'target_seat':agent,'unit':unit,'scheme':scheme,'match':match,**uptake(sus,out_ids,adj,field,scheme)})
  for o in r['outcomes']:
   rd=o['round'];acc.append({'case':cid,'condition':cond,'round':rd,'level':'literal_system',**accuracy(o['answer'],r['reference'])})
   ps=[t['answer'] for t in o['agent_results']];edges=[]
   for i,j in itertools.combinations(range(3),2):
    if judge_label(ps[i],ps[j])=='S':edges.append((i,j))
   # Pair labels need not be transitive. Do not choose an arbitrary tied clique.
   if len(edges)==2:answer=None;ambiguity=True
   elif len(edges)>=1:
    members=set(x for e in edges for x in e);answer=sorted((ps[i] for i in members),key=lambda x:(norm(x),x))[0];ambiguity=False
   else:answer=None;ambiguity=False
   acc.append({'case':cid,'condition':cond,'round':rd,'level':'semantic_system','nontransitive_vote':ambiguity,**accuracy(answer,r['reference'])})
  print(cond,cid,flush=True)
 assert len(profiles)==8640 and len(graphs)==17280 and len(acc)==1800
 # Average within each case before across-case inference; agents are not independent patients.
 def aggregate(rows,keys,metrics):
  groups=defaultdict(list)
  for row in rows:groups[tuple(row[k] for k in keys)].append(row)
  out=[]
  for key,rs in groups.items():
   result=dict(zip(keys,key));result['cases']=len({r['case'] for r in rs});result['metrics']={}
   for m in metrics:
    bycase=defaultdict(list)
    for r in rs:bycase[r['case']].append(r.get(m))
    result['metrics'][m]=summarize([avg(v) for v in bycase.values()])
   out.append(result)
  return out
 psummary=aggregate(profiles,['condition','round','field','unit','scheme','match'],METRICS+['output_facts','input_facts','own_den','other_den','own_num','other_num'])
 gsummary=aggregate(graphs,['condition','round','from','to','unit','scheme','match'],['uptake_own','uptake_other','uptake_prime','own_den','other_den','own_num','other_num'])
 csummary=aggregate(counts,['condition','round','mode','scope'],['facts','atoms','new_vs_outputs','new_vs_initial','cumulative_facts'])
 asum=aggregate(acc,['condition','round','level'],['exact','fuzzy_same','fuzzy_inclusive','fuzzy_upper','uncertain','abstain'])
 esummary=[]
 for condition in CONDS:
  for rd in [1,2,3]:
   for mode in ['equivalence','entailment']:
    for scheme in ['inclusive','fractional']:
     rs=[r for r in counts if r['condition']==condition and r['round']==rd and r['mode']==mode]
     esummary.append({'condition':condition,'round':rd,'mode':mode,'scheme':scheme,'entropy':summarize([r[scheme]['entropy_bits'] for r in rs]),'effective_types':summarize([r[scheme]['effective_types'] for r in rs]),'distribution':{t:avg([r[scheme]['distribution'][t] for r in rs]) for t in TAGS}})
 # Precompute paired condition contrasts and round contrasts for every requested role/weighting.
 contrasts=[];caseids=sorted({r['case'] for r in runs});lookup=defaultdict(list)
 for r in profiles:
  for field in [r['field'],'all']:lookup[(r['condition'],r['round'],field,r['unit'],r['scheme'],r['match'],r['case'])].append(r)
 pairs=[('Roles · shared','shared-specialist','shared-generic'),('Roles · split','split-specialist','split-generic'),('Split information · generic','split-generic','shared-generic'),('Split information · specialist','split-specialist','shared-specialist'),('Role mismatch · split','split-mismatched','split-specialist')]
 for unit,scheme,match,field in itertools.product(['equivalence','atoms'],['inclusive','fractional'],['equivalence','entailment'],FIELDS+['all']):
  comparisons=[(name,a,rd,b,rd) for name,a,b in pairs for rd in [1,2,3]]+[(f'R{r2} − R{r1}',c,r2,c,r1) for c in CONDS for r1,r2 in [(1,2),(2,3),(1,3)]]
  for name,a,ar,b,br in comparisons:
   row={'name':name,'a':a,'ar':ar,'b':b,'br':br,'unit':unit,'scheme':scheme,'match':match,'field':field,'metrics':{}}
   for metric in METRICS:
    differences=[]
    for cid in caseids:
     va=avg([x[metric] for x in lookup[(a,ar,field,unit,scheme,match,cid)]]);vb=avg([x[metric] for x in lookup[(b,br,field,unit,scheme,match,cid)]])
     differences.append(va-vb if va is not None and vb is not None else None)
    row['metrics'][metric]=summarize(differences)
   contrasts.append(row)

 acc_contrasts=[];alook=defaultdict(list)
 for row in acc:alook[(row['condition'],row['round'],row['level'],row['case'])].append(row)
 for level in ['agent','literal_system','semantic_system']:
  comparisons=[(name,a,rd,b,rd) for name,a,b in pairs for rd in [1,2,3]]+[(f'R{r2} − R{r1}',c,r2,c,r1) for c in CONDS for r1,r2 in [(1,2),(2,3),(1,3)]]
  for name,a,ar,b,br in comparisons:
   row={'name':name,'a':a,'ar':ar,'b':b,'br':br,'level':level,'metrics':{}}
   for metric in ['exact','fuzzy_same','fuzzy_inclusive']:
    diffs=[]
    for cid in caseids:
     va=avg([x[metric] for x in alook[(a,ar,level,cid)]]);vb=avg([x[metric] for x in alook[(b,br,level,cid)]])
     diffs.append(va-vb)
    row['metrics'][metric]=summarize(diffs)
   acc_contrasts.append(row)
 raw={'profiles':profiles,'graphs':graphs,'counts':counts,'accuracy':acc,'role_mapping':mapping,'component_diagnostics':component_diagnostics}
 audit={'traces':120,'cases':24,'turns':1080,'profile_rows':len(profiles),'graph_rows':len(graphs),'accuracy_rows':len(acc),'judgment':{k:v for k,v in judge.items() if k!='labels'},'judge_pair_count':len(labels),'review_corrections':len(review['corrections']),'judge_label_counts':dict(Counter(labels.values())),'source_viewer_sha256':hashlib.sha256((ROOT/'findings/medcase24-trace-viewer.html').read_bytes()).hexdigest(),'method':'Exact equality uses casefold, whitespace normalization and trailing period removal. Fuzzy is name-only, not case-supported adjudication. Semantic voting uses only S-equivalence between agent names; no reference-aware vote.'}
 payload={'conditions':CONDS,'fields':FIELDS,'tags':TAGS,'mapping':MAP,'profiles':psummary,'graphs':gsummary,'counts':csummary,'accuracy':asum,'accuracy_contrasts':acc_contrasts,'entropy':esummary,'contrasts':contrasts,'components':aggregate(component_diagnostics,['condition'],['largest_equivalence_share','largest_entailment_share','equivalence_groups','entailment_groups']),'audit':audit,'raw_accuracy':acc,'role_mapping':mapping,'judge_review':review['corrections'],'judge_audit':[{'id':i,'names':json.loads((OUT/'config.json').read_text())['pairs'][i],'label':l,'model_label':judge['labels'][i]} for i,l in labels.items()]}
 # Invariants: input-source rates are bounded; prime is a difference, not a ratio of pooled totals.
 for r in profiles+graphs:
  for k in ['uptake_own','uptake_other']:
   assert r[k] is None or -1e-10<=r[k]<=1+1e-10
  assert r['own_num']<=r['own_den']+1e-10 and r['other_num']<=r['other_den']+1e-10
 for r in profiles:
  if r['scheme']=='fractional':assert r['output_own']+r['output_other']<=1+1e-10
 for r in counts:
  if r['round']>0:assert 0<=r['new_vs_initial']<=r['new_vs_outputs']<=r['facts']
 (DEST/'observations.json').write_text(json.dumps(raw,ensure_ascii=False,separators=(',',':'),allow_nan=False))
 (DEST/'summary.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False))
 (DEST/'audit.json').write_text(json.dumps(audit,indent=2))
 print(json.dumps(audit,indent=2))
if __name__=='__main__':
 main()
 from followup import extend
 extend(json.loads((DEST/'summary.json').read_text()))
 from social_uptake import main as analyze_social
 analyze_social()
