"""Small, resumable name-only judge. Explicit no-thinking and USD 0.10 ceiling."""
from pathlib import Path
import json,re,hashlib,os,shlex,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'runs/medcase24-name-judge-20260910-v2'
PRICE={'input':.30,'output':1.20,'cache_read':.06,'source':'https://opencode.ai/docs/go/','checked_utc':'2026-09-10','unit':'USD per million tokens'}
SYSTEM='''Classify the NAMING relationship between two diagnosis strings. You have NO patient context. No reasoning or explanations. Return ONLY {"labels":[[id,code],...]} in input order.
S: Same disease AND same diagnostic specificity. Only spelling, spacing, punctuation, standard synonyms or unambiguous abbreviations differ. Both directions must be synonymous.
L: A definite direct disease parent/subtype or site/age-specific refinement. One is explicitly a type of the other. Merely overlapping, co-occurring, causing similar symptoms or sharing an ancestor is NOT L. A parent is NOT S.
D: Different diseases, sibling diseases, incompatible etiology/subtypes, or an uninformative generic symptom/category. Similar presentation does not earn credit.
U: A cause/complication association that might fit a particular case, or genuinely ambiguous names; case context would be needed. Never infer a causal story to award S or L.
Examples: myocardial infarction / heart attack S; cysticfibrosis / cystic fibrosis S; Charcot arthropathy / neuropathic arthropathy S; familial glucocorticoid deficiency / primary adrenal insufficiency L; giant cell arteritis / systemic vasculitis L; juvenile systemic sclerosis / systemic sclerosis L; pelvic actinomycosis / actinomycosis L; giant cell arteritis / Takayasu arteritis D (siblings, neither is a subtype of the other); bacterial pneumonia / viral pneumonia D; juvenile idiopathic arthritis / chronic recurrent multifocal osteomyelitis D; pneumonia / cough D; tumor / lymphoma D; lung cancer / ectopic ACTH syndrome U; phosphaturic mesenchymal tumor / tumor-induced osteomalacia U; fracture / fat embolism U. Broad labels must not be promoted to exact synonyms. Output codes only.'''
def norm(s):return ' '.join(str(s or '').casefold().split()).rstrip('.')
def pair(a,b):return tuple(sorted((norm(a),norm(b))))
def pid(a,b):return hashlib.sha256(json.dumps(pair(a,b),ensure_ascii=False).encode()).hexdigest()[:24]
def load_runs():
 p=ROOT/'findings/medcase24-trace-viewer.html';return json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>',p.read_text(),re.S)[1])['runs']
def atomic(path,obj):
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));os.replace(temp,path)
def main():
 OUT.mkdir(exist_ok=True,parents=True);(OUT/'calls').mkdir(exist_ok=True)
 needed={}
 def add(a,b):
  if a and b and norm(a)!=norm(b):needed[pid(a,b)]=pair(a,b)
 for r in load_runs():
  for c in r['cards']:
   if c['channel']=='output':add(c['diagnosis'],r['reference'])
  for o in r['outcomes']:
   add(o['answer'],r['reference']);preds=[t['answer'] for t in o['agent_results']]
   for i,a in enumerate(preds):
    for b in preds[i+1:]:add(a,b)
 pending=sorted(needed);config={'model':'minimax-m3','endpoint':'https://opencode.ai/zen/go/v1/messages','api_key_env':'OPENCODE_API_KEY_2','thinking':{'type':'disabled'},'max_tokens':512,'batch_size':12,'budget_usd':.10,'prices':PRICE,'system':SYSTEM,'pairs':needed,'scope':'Names only; S synonym match; S+L inclusive name-level compatibility. S+L includes definite taxonomic refinements only. Causal associations are U. Case-supported correctness is not established.'}
 if (OUT/'config.json').exists():assert json.loads((OUT/'config.json').read_text())==json.loads(json.dumps(config))
 else:atomic(OUT/'config.json',config)
 # Read only the requested key; never print it or include headers in audit files.
 key=os.environ.get('OPENCODE_API_KEY_2')
 if not key:
  for line in (ROOT/'.env').read_text().splitlines():
   if line.startswith('OPENCODE_API_KEY_2='):key=shlex.split(line.split('=',1)[1])[0]
 if not key:raise ValueError('Missing API 2')
 state=json.loads((OUT/'results.json').read_text()) if (OUT/'results.json').exists() else {'labels':{},'charged_or_reserved_usd':0.,'usage':{'input_tokens':0,'output_tokens':0,'cache_read_input_tokens':0},'thinking_blocks':0,'complete':False}
 # Budget is reconciled from all attempts, including failures, before dispatch.
 attempts=[json.loads(p.read_text()) for p in (OUT/'calls').glob('*.json')]
 prior=sum(json.loads(f.read_text())['cost_or_reserve_usd'] for folder in (ROOT/'runs').glob('medcase24-name-judge-20260910*') if folder!=OUT for f in (folder/'calls').glob('*.json'))
 state['charged_or_reserved_usd']=prior+sum(a['cost_or_reserve_usd'] for a in attempts)
 state['prior_versions_usd']=prior
 remaining=[i for i in pending if i not in state['labels']]
 for start in range(0,len(remaining),12):
  ids=remaining[start:start+12];items=[[i,*needed[i]] for i in ids]
  request={'model':config['model'],'system':SYSTEM,'messages':[{'role':'user','content':json.dumps(items,ensure_ascii=False,separators=(',',':'))}],'thinking':{'type':'disabled'},'max_tokens':512,'temperature':0,'stream':False}
  body=json.dumps(request,ensure_ascii=False).encode();reserve=((len(body)+1024)*PRICE['input']+512*PRICE['output'])/1e6
  if state['charged_or_reserved_usd']+reserve>.095:raise RuntimeError('Budget guard: stop before USD 0.10')
  callfile=OUT/'calls'/f'{time.time_ns()}.json';log={'request':request,'cost_or_reserve_usd':reserve,'status':'reserved','prices':PRICE};atomic(callfile,log);state['charged_or_reserved_usd']+=reserve;atomic(OUT/'results.json',state)
  started=time.monotonic()
  try:
   req=urllib.request.Request(config['endpoint'],data=body,headers={'Content-Type':'application/json','x-api-key':key,'anthropic-version':'2023-06-01','User-Agent':'clinical-factflow/0.1','x-opencode-session':'clinical-factflow-name-judge-20260910'},method='POST')
   with urllib.request.urlopen(req,timeout=120) as f:raw=json.load(f)
   log['response']=raw;usage=raw.get('usage',{});assert all(k in usage for k in ['input_tokens','output_tokens'])
   assert not usage.get('cache_creation_input_tokens',0)
   cost=(usage['input_tokens']*.30+usage['output_tokens']*1.20+usage.get('cache_read_input_tokens',0)*.06)/1e6
   log['cost_or_reserve_usd']=cost;state['charged_or_reserved_usd']+=cost-reserve
   thinking=sum(b['type']=='thinking' for b in raw['content']);state['thinking_blocks']+=thinking
   assert not thinking and not usage.get('reasoning_tokens',0),'Thinking emitted: stop'
   assert raw.get('stop_reason')=='end_turn';text=''.join(b['text'] for b in raw['content'] if b['type']=='text');parsed=json.loads(text);labels=parsed['labels'] if isinstance(parsed,dict) else parsed;assert [x[0] for x in labels]==ids and all(len(x)==2 and x[1] in ['S','L','D','U'] for x in labels)
   state['labels'].update(dict(labels))
   for k in state['usage']:state['usage'][k]+=usage.get(k,0)
   log['status']='complete';print(json.dumps({'labeled':len(state['labels']),'total':len(needed),'usd':state['charged_or_reserved_usd'],'seconds':round(time.monotonic()-started,2)}),flush=True)
  except Exception as e:
   log['status']='failed';log['error_type']=type(e).__name__;raise
  finally:
   log['seconds']=time.monotonic()-started;atomic(callfile,log);atomic(OUT/'results.json',state)
 state['complete']=len(state['labels'])==len(needed);atomic(OUT/'results.json',state)
if __name__=='__main__':main()
