"""Exploratory fact-to-outcome audit with case clustering and held-out cases. Offline."""
from analyze import *
from scipy.stats import t as student_t
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,brier_score_loss,log_loss
OUTCOME=ROOT/'findings/medcase24-fact-outcome'
FEATURES=['r1_density','r1_evidence','r1_entropy','r1_overlap','r2_evidence','r2_entropy','r2_novel','r2_prime','peer','new_peer','self','compression12']
NAMES=['R1 fact density','R1 evidence coverage','R1 domain entropy','R1 peer overlap','R2 evidence coverage','R2 domain entropy','R2 novel fact share','R2 professional uptake prime','R1→R2 peer uptake','R1→R2 new-to-peer uptake','R1→R2 self retention','R1–R2 compression']
SEED=20260913

def make_rows():
 O=json.loads((DEST/'observations.json').read_text());S=json.loads((DEST/'social-uptake-observations.json').read_text());T=json.loads((ROOT/'findings/medcase24-figures/token-clock.json').read_text())
 acc={(r['case'],r['condition'],r['round'],r.get('seat',r['level'])):r for r in O['accuracy']}
 tok={(r['case'],r['condition'],r['round']):r['tokens'] for r in T['runs']}
 panels={(p['case'],p['condition'],p['round']):p for p in S['panels']}
 ps={(r['case'],r['condition'],r['round'],r['seat']):r for r in O['profiles'] if r['unit']=='equivalence' and r['scheme']=='fractional' and r['match']=='equivalence'}
 rows=[];edges=[]
 for run in load_runs():
  cid,cond=run['case'],run['condition'];card={c['id']:c for c in run['cards']};eq=[(a,b) for a,b,x,y in run['scores'] if min(x,y)>=5.28];adj=defaultdict(set)
  for a,b in eq:adj[a].add(b);adj[b].add(a)
  ids={rd:{f['id'] for c in card.values() if c['channel']=='output' and c['round']==rd for f in c['facts']} for rd in [1,2]}
  us={rd:units([c for c in card.values() if c['channel']=='output' and c['round']==rd],eq,'equivalence') for rd in [1,2]}
  evidence=units([c for c in card.values() if c['channel']=='source'],eq,'equivalence')
  r={'case':cid,'condition':cond,'final_label':acc[cid,cond,3,'semantic_system']['label'],'y':acc[cid,cond,3,'semantic_system']['fuzzy_inclusive'],'y_same':acc[cid,cond,3,'semantic_system']['fuzzy_same'],'r1_correct':avg([acc[cid,cond,1,s]['fuzzy_inclusive'] for s in ['A','B','C']]),'r2_correct':avg([acc[cid,cond,2,s]['fuzzy_inclusive'] for s in ['A','B','C']]),'r1_consensus':{'unanimous':1.,'two_one':1/3,'nontransitive':2/3,'all_different':0.}[panels[cid,cond,1]['kind']],'log_tokens':math.log(tok[cid,cond,1]),'r1_density':len(us[1])/tok[cid,cond,1]*100,'r2_novel':avg([not retained(u,ids[1],adj) for u in us[2]]),'r2_prime':avg([ps[cid,cond,2,s]['uptake_prime'] for s in ['A','B','C']]),'compression12':1-len(components(ids[1]|ids[2],eq))/(len(us[1])+len(us[2]))}
  for rd in [1,2]:
   r[f'r{rd}_evidence']=avg([retained(u,ids[rd],adj) for u in evidence]);r[f'r{rd}_entropy']=entropy(us[rd],'fractional')['entropy_normalized']
  pair=[]
  for a,b in itertools.combinations(['A','B','C'],2):
   ua=units([card[a+'|1']],eq,'equivalence');ub=units([card[b+'|1']],eq,'equivalence');ia={x for u in ua for x in u['ids']};ib={x for u in ub for x in u['ids']};pair.append(.5*(avg([retained(u,ib,adj) for u in ua])+avg([retained(u,ia,adj) for u in ub])))
  r['r1_overlap']=avg(pair)
  er=[];diagshares=[]
  for a in ['A','B','C']:
   ua=units([card[a+'|1']],eq,'equivalence');diagshares.append(sum('diagnosis' in u['tags'] for u in ua)/len(ua));nodiag=[u for u in ua if 'diagnosis' not in u['tags']]
   for b in ['A','B','C']:
    now={f['id'] for f in card[b+'|2']['facts']};old={f['id'] for f in card[b+'|1']['facts']};new=[u for u in ua if not retained(u,old,adj)];newnd=[u for u in nodiag if not retained(u,old,adj)]
    saved=next(e for e in S['edges'] if e['case']==cid and e['condition']==cond and e['round']==1 and e['seat']==a and e['target']==b and e['unit']=='equivalence' and e['scope']=='all' and e['match']=='equivalence')
    edge={'case':cid,'condition':cond,'panel':cid+'|'+cond,'source':a,'target':b,'source_label':acc[cid,cond,1,a]['label'],'target_label':acc[cid,cond,1,b]['label'],'source_correct':acc[cid,cond,1,a]['fuzzy_inclusive'],'target_correct':acc[cid,cond,1,b]['fuzzy_inclusive'],'prior_same':float(saved['prior_same_answer']),'log_source_facts':math.log(len(ua)),'prior_overlap':1-len(new)/len(ua),'rate':avg([retained(u,now,adj) for u in ua]),'new_rate':avg([retained(u,now,adj) for u in new]),'nodiag_rate':avg([retained(u,now,adj) for u in nodiag]),'new_nodiag_rate':avg([retained(u,now,adj) for u in newnd])}
    er.append(edge);edges.append(edge)
  for name,key,peer in [('peer','rate',True),('new_peer','new_rate',True),('self','rate',False),('peer_nodiag','nodiag_rate',True),('new_peer_nodiag','new_nodiag_rate',True)]:r[name]=avg([e[key] for e in er if (e['source']!=e['target'])==peer])
  r['r1_diagnosis_share']=avg(diagshares);r['prior_peer_overlap']=avg([e['prior_overlap'] for e in er if e['source']!=e['target']]);rows.append(r)
 return rows,edges

def demean(a,groups):
 a=a.copy()
 for g in set(groups):
  ix=np.where(np.asarray(groups)==g)[0];a[ix]-=a[ix].mean(axis=0)
 return a

def fit(rows,key,outcome='y',controls=None,fe='case',scale=True,boot=2000):
 controls=controls or [];rs=[r for r in rows if all(finite(r.get(k)) for k in [key,outcome]+controls)];n=len(rs);cases=sorted({r['case'] for r in rs});ci=np.array([cases.index(r['case']) for r in rs]);g=len(cases)
 sd=float(np.std([r[key] for r in rs],ddof=1)) if scale else 1.
 if sd<1e-10:return {'key':key,'n':n,'cases':g,'mean':None}
 x=np.array([r[key]/sd for r in rs]);y=np.array([r[outcome] for r in rs]);cols=[x]+[np.array([r[k] for r in rs]) for k in controls]
 if fe=='case':cols += [np.array([float(r['condition']==c) for r in rs]) for c in CONDS[1:]]
 if fe is None:cols+=[np.ones(n)]
 X=np.array(cols).T;groups=[r[fe] for r in rs] if fe else []
 if fe:X=demean(X,groups);y=demean(y,groups)
 A=X.T@X;inv=np.linalg.pinv(A);beta=inv@(X.T@y);resid=y-X@beta
 scores=np.array([X[ci==i].T@resid[ci==i] for i in range(g)]);rank=np.linalg.matrix_rank(X)+(len(set(groups)) if fe else 0);correction=g/(g-1)*(n-1)/max(1,n-rank);cov=inv@(scores.T@scores)@inv*correction;se=float(np.sqrt(max(0,cov[0,0])));p=float(2*student_t.sf(abs(beta[0])/se,g-1)) if se else 0.
 # Case bootstrap after within-case/panel demeaning; all rows of a sampled case travel together.
 xx=np.array([X[ci==i].T@X[ci==i] for i in range(g)]);xy=np.array([X[ci==i].T@y[ci==i] for i in range(g)]);weights=np.random.default_rng(SEED).multinomial(g,np.repeat(1/g,g),size=boot);AA=np.einsum('bg,gij->bij',weights,xx);BB=weights@xy;bs=np.einsum('bij,bj->bi',np.linalg.pinv(AA),BB)[:,0]
 # Partial-residual points for an auditable plot, not independent observations.
 Z=X[:,1:];rx=X[:,0]-Z@np.linalg.lstsq(Z,X[:,0],rcond=None)[0];ry=y-Z@np.linalg.lstsq(Z,y,rcond=None)[0]
 return {'key':key,'mean':float(beta[0]),'lo':float(np.quantile(bs,.025)),'hi':float(np.quantile(bs,.975)),'se':se,'p':p,'n':n,'cases':g,'scale_sd':sd,'controls':controls,'fe':fe,'points':[{'case':r['case'],'condition':r['condition'],'x':float(a),'y':float(b)} for r,a,b in zip(rs,rx,ry)]}

def bh(rs):
 q=1
 for i,r in reversed(list(enumerate(sorted(rs,key=lambda r:r['p']),1))):q=min(q,r['p']*len(rs)/i);r['q']=q

def cv(rows):
 cases=sorted({r['case'] for r in rows});y=np.array([r['y'] for r in rows]);ci=np.array([cases.index(r['case']) for r in rows]);condition=np.array([[float(r['condition']==c) for c in CONDS[1:]] for r in rows]);models={};predictions={}
 for oracle in [False,True]:
  base=['log_tokens','r1_consensus']+(['r1_correct'] if oracle else [])
  for add in [False,True]:
   keys=base+(FEATURES if add else []);X=np.column_stack([condition,np.array([[r[k] if r[k] is not None else np.nan for k in keys] for r in rows])]);pred=np.zeros(len(rows))
   for case in cases:
    test=np.array([r['case']==case for r in rows]);m=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(C=1.,max_iter=2000,solver='lbfgs'));m.fit(X[~test],y[~test]);pred[test]=m.predict_proba(X[test])[:,1]
   case_loss=np.array([np.mean((y[ci==i]-pred[ci==i])**2) for i in range(len(cases))]);bi=np.random.default_rng(SEED).integers(0,len(cases),(2000,len(cases)));bci=np.quantile(case_loss[bi].mean(axis=1),[.025,.975])
   name=('oracle' if oracle else 'observable')+('_facts' if add else '_baseline');predictions[name]=pred;models[name]={'brier_lo':float(bci[0]),'brier_hi':float(bci[1]),'brier':brier_score_loss(y,pred),'auc':roc_auc_score(y,pred),'log_loss':log_loss(y,pred),'features':keys,'predictions':pred.tolist()}
 comparison=[];ix=np.random.default_rng(SEED).integers(0,len(cases),(2000,len(cases)))
 for prefix in ['observable','oracle']:
  a=predictions[prefix+'_baseline'];b=predictions[prefix+'_facts'];case_delta=np.array([np.mean((y[ci==i]-a[ci==i])**2-(y[ci==i]-b[ci==i])**2) for i in range(len(cases))]);bs=case_delta[ix].mean(axis=1);comparison.append({'baseline':prefix,'brier_improvement':float(case_delta.mean()),'lo':float(np.quantile(bs,.025)),'hi':float(np.quantile(bs,.975)),'case_differences':case_delta.tolist()})
 return {'models':models,'comparisons':comparison,'cases':cases,'y':y.tolist(),'method':'leave-one-case-out; all 5 conditions held out together; fixed C=1; bootstrap of held-out case losses (training uncertainty not included)'}

def main():
 OUTCOME.mkdir(parents=True,exist_ok=True);rows,edges=make_rows();(OUTCOME/'observations.json').write_text(json.dumps({'traces':rows,'edges':edges},separators=(',',':'),allow_nan=False));print('Built rows',len(rows),flush=True)
 tests=[];sensitivity=[]
 for key,name in zip(FEATURES,NAMES):
  a=fit(rows,key,controls=['log_tokens','r1_correct']);a['name']=name;tests.append(a)
  for tag,rs,out,ctrl in [('raw',rows,'y',[]),('no_initial_correctness',rows,'y',['log_tokens']),('exclude_U',[r for r in rows if r['final_label']!='U'],'y',['log_tokens','r1_correct']),('same_only',rows,'y_same',['log_tokens','r1_correct']),('adjust_R2_correctness',rows,'y',['log_tokens','r1_correct','r2_correct'])]:
   z=fit(rs,key,out,ctrl,fe=None if tag=='raw' else 'case');sensitivity.append(dict(z,sensitivity=tag))
  print(key,round(a['mean']*100,2),round(a['lo']*100,2),round(a['hi']*100,2),flush=True)
 bh(tests)
 nodiag=[fit(rows,k,controls=['log_tokens','r1_correct']) for k in ['peer_nodiag','new_peer_nodiag']]
 es=[e for e in edges if e['source']!=e['target'] and e['source_label'] in ['S','L','D'] and e['target_label'] in ['S','L','D']];upstream=[]
 for outcome in ['rate','new_rate','nodiag_rate','new_nodiag_rate']:
  for controls,tag in [([], 'within_panel'),(['target_correct','prior_same','prior_overlap','log_source_facts'],'prior_state_adjusted')]:
   z=fit(es,'source_correct',outcome,controls,'panel',False);upstream.append(dict(z,measure=outcome,adjustment=tag))
 # Predictors of early peer uptake without conditioning on final outcome.
 mechanism=[]
 for key in ['prior_same','prior_overlap','target_correct']:
  other=[k for k in ['source_correct','target_correct','prior_same','prior_overlap','log_source_facts'] if k!=key];z=fit(es,key,'rate',other,'panel',False);mechanism.append(z)
 validation=cv(rows)
 inventory={'traces':len(rows),'cases':len({r['case'] for r in rows}),'final_labels':dict(Counter(r['final_label'] for r in rows)),'outcome_varying_cases':sum(len({r['y'] for r in rows if r['case']==c})>1 for c in {r['case'] for r in rows}),'edge_rows_known':len(es),'r1_zero_correct':sum(r['r1_correct']==0 for r in rows),'r1_zero_correct_final_success':sum(r['r1_correct']==0 and r['y']==1 for r in rows)}
 result={'inventory':inventory,'features':FEATURES,'tests':tests,'sensitivity':sensitivity,'nodiag':nodiag,'upstream':upstream,'mechanism':mechanism,'cv':validation,'policy':{'primary':'one standardized feature per model; case + condition fixed effects, log R1 tokens, R1 accepted agent fraction','CI':'2000 case bootstrap; p case-cluster sandwich t(df=G-1); BH family of 12 primary coefficients','outcome':'R3 semantic-system S or L accepted. U coded not accepted in main analysis; U excluded sensitivity. D definite different diagnosis.','timing':'No R3 facts in any predictor. R1→R2 only for uptake. All exploratory; mediators and latent reasoning confound causal interpretation.','source_truth':'Source diagnosis correctness is not the correctness of every fact in that source.'}}
 (OUTCOME/'analysis.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False));print('INVENTORY',inventory,flush=True);print('CV',validation['comparisons'],flush=True)
 for r in upstream:print('UPSTREAM',r['measure'],r['adjustment'],r['mean'],r['lo'],r['hi'],flush=True)
 for r in mechanism:print('MECHANISM',r['key'],r['mean'],r['lo'],r['hi'],flush=True)
if __name__=='__main__':main()
