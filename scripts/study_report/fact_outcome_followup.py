"""Targeted robustness after the fixed 12-metric audit. Explicitly exploratory."""
from fact_outcome import *

def main():
 D=json.loads((OUTCOME/'analysis.json').read_text());O=json.loads((OUTCOME/'observations.json').read_text());rows=O['traces'];edges=O['edges'];bykey={(r['case'],r['condition']):r for r in rows}
 for run in load_runs():
  row=bykey[run['case'],run['condition']];eq=[(a,b) for a,b,x,y in run['scores'] if min(x,y)>=5.28];adj=defaultdict(set)
  for a,b in eq:adj[a].add(b);adj[b].add(a)
  ev=[u for u in units([c for c in run['cards'] if c['channel']=='source'],eq,'equivalence') if 'diagnosis' not in u['tags']]
  ids={rd:{f['id'] for c in run['cards'] if c['channel']=='output' and c['round']==rd for f in c['facts'] if 'diagnosis' not in f['annotation']['clinical_domain']} for rd in [1,2]}
  for rd in [1,2]:row[f'r{rd}_evidence_nodiag']=avg([retained(u,ids[rd],adj) for u in ev])
  row['evidence_gain']=row['r2_evidence']-row['r1_evidence']
 extra=[]
 for key,ctrl in [('r2_evidence',['log_tokens','r1_correct','r1_evidence']),('evidence_gain',['log_tokens','r1_correct','r1_evidence']),('r2_evidence_nodiag',['log_tokens','r1_correct']),('r2_evidence_nodiag',['log_tokens','r1_correct','r1_evidence_nodiag'])]:extra.append(fit(rows,key,controls=ctrl))
 # Paired case bootstrap for all-fact versus no-diagnosis source correctness contrasts.
 es=[e for e in edges if e['source']!=e['target'] and e['source_label'] in ['S','L','D'] and e['target_label'] in ['S','L','D'] and e['nodiag_rate'] is not None];cases=sorted({e['case'] for e in es});x=demean(np.array([[e['source_correct']] for e in es]),[e['panel'] for e in es])[:,0]
 y=demean(np.array([[e['rate'],e['nodiag_rate']] for e in es]),[e['panel'] for e in es]);den=np.array([np.sum(x[[e['case']==c for e in es]]**2) for c in cases]);num=np.array([x[[e['case']==c for e in es]]@y[[e['case']==c for e in es]] for c in cases]);weights=np.random.default_rng(SEED).multinomial(len(cases),np.repeat(1/len(cases),len(cases)),size=2000);bs=(weights@num)/(weights@den)[:,None];diff=bs[:,0]-bs[:,1];center=num.sum(axis=0)/den.sum();paired={'all':float(center[0]),'nodiag':float(center[1]),'difference':float(center[0]-center[1]),'lo':float(np.quantile(diff,.025)),'hi':float(np.quantile(diff,.975)),'n':len(es),'cases':len(cases)}
 initial=[]
 for correct_n in [0,1,2,3]:
  rs=[r for r in rows if round(3*r['r1_correct'])==correct_n];caseids=sorted({r['case'] for r in rows});rng=np.random.default_rng(SEED);boot=[]
  for ix in rng.integers(0,len(caseids),(2000,len(caseids))):
   vals=[r['y'] for i in ix for r in rs if r['case']==caseids[i]]
   if vals:boot.append(np.mean(vals))
  initial.append({'r1_correct_agents':correct_n,'n':len(rs),'successes':sum(r['y'] for r in rs),'rate':avg([r['y'] for r in rs]),'lo':float(np.quantile(boot,.025)),'hi':float(np.quantile(boot,.975)),'cases':len({r['case'] for r in rs})})
 # Joint model is an exploratory check on redundancy among the two leading metrics.
 joint=[fit(rows,key,controls=['log_tokens','r1_correct',other]) for key,other in [('r2_evidence','compression12'),('compression12','r2_evidence')]]
 D['targeted']={'extra':extra,'diagnosis_ablation_difference':paired,'initial_correctness':initial,'joint':joint,'notice':'Added after viewing the fixed 12-metric audit. No new confirmatory family; do not interpret as independent replications.'}
 (OUTCOME/'analysis.json').write_text(json.dumps(D,separators=(',',':'),allow_nan=False));(OUTCOME/'observations.json').write_text(json.dumps(O,separators=(',',':'),allow_nan=False))
 for r in extra:print(r['key'],r['controls'],r['mean'],r['lo'],r['hi'])
 print('DIAG ABLATION',paired);print('INITIAL',initial)
if __name__=='__main__':main()
