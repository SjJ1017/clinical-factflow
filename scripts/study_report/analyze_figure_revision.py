"""Offline audits for cumulative deduplication, novelty, domain denominators and pooled inference."""
from analyze import *
from scipy.stats import t
DEST2=ROOT/'findings/medcase24-figures'

def stat(v):
    s=summarize(v);a=np.array([x for x in v if finite(x)])
    s['t_lo']=s['t_hi']=None
    if len(a)<2:s['lo']=s['hi']=None
    else:
        h=float(t.ppf(.975,len(a)-1)*a.std(ddof=1)/np.sqrt(len(a)));s['t_lo']=s['mean']-h;s['t_hi']=s['mean']+h
    return s

def case_values(edges, group_key=None):
    """Mean recipient rate -> source/round -> group within panel -> rounds -> conditions -> case."""
    source=defaultdict(list)
    for e in edges:
        if e['rate'] is not None:source[(e['case'],e['condition'],e['round'],e['seat'])].append(e['rate'])
    panel=defaultdict(list)
    for (case,cond,rd,seat),v in source.items():panel[(case,cond,rd)].append(avg(v))
    condition=defaultdict(list)
    for (case,cond,rd),v in panel.items():condition[(case,cond)].append(avg(v))
    case=defaultdict(list)
    for (cid,cond),v in condition.items():case[cid].append(avg(v))
    return {cid:avg(v) for cid,v in case.items()}

def paired_test(edges,key,plus,minus):
    source=defaultdict(list)
    for e in edges:
        if e['rate'] is not None:source[(e['case'],e['condition'],e['round'],e['seat'],e[key])].append(e['rate'])
    panels=defaultdict(lambda:defaultdict(list))
    for (case,cond,rd,seat,g),v in source.items():panels[(case,cond,rd)][g].append(avg(v))
    bycondition=defaultdict(list);n=0
    for (case,cond,rd),groups in panels.items():
        if plus in groups and minus in groups:bycondition[(case,cond)].append(avg(groups[plus])-avg(groups[minus]));n+=1
    bycase=defaultdict(list)
    for (case,cond),v in bycondition.items():bycase[case].append(avg(v))
    values=[avg(v) for v in bycase.values()];s=stat(values);p=None
    if len(values)>=2:
        a=np.asarray(values);obs=abs(a.mean())
        if len(a)<=16:
            signs=1-2*((np.arange(2**len(a))[:,None]>>np.arange(len(a)))&1);p=float(np.mean(abs((signs*a).mean(axis=1))>=obs-1e-12))
        else:
            signs=np.random.default_rng(20260911).choice([-1,1],size=(100000,len(a)));p=float((1+np.sum(abs((signs*a).mean(axis=1))>=obs-1e-12))/100001)
    return {'effect':s,'p':p,'q':None,'panels':n,'case_gaps':dict(zip(bycase,values))}

def main():
    D=json.loads((DEST/'summary.json').read_text());O=json.loads((DEST/'observations.json').read_text());runs=load_runs()
    role={(r['case'],r['condition']):r['role_by_seat'] for r in D['role_mapping']};novel=[];repeat=[];domain=[]
    for run in runs:
        eq=[];adj=defaultdict(set)
        for a,b,x,y in run['scores']:
            if min(x,y)>=5.28:eq.append((a,b));adj[a].add(b);adj[b].add(a)
        outs=[c for c in run['cards'] if c['channel']=='output'];initial=[c for c in run['cards'] if c['channel']!='output']
        initialids={f['id'] for c in initial for f in c['facts']};roundids={rd:{f['id'] for c in outs if c['round']==rd for f in c['facts']} for rd in [1,2,3]}
        ids=set.union(*roundids.values());groups=components(ids,eq)
        presences=sum(sum(bool(g&roundids[rd]) for rd in [1,2,3]) for g in groups)
        sumround=sum(len(components(roundids[rd],eq)) for rd in [1,2,3]);multi=sum(sum(bool(g&roundids[rd]) for rd in [1,2,3])>1 for g in groups)
        repeat.append({'case':run['case'],'condition':run['condition'],'sum_round_facts':sumround,'trace_facts':len(groups),'fixed_cluster_round_presences':presences,'repeat_excess':presences-len(groups),'bridge_reduction':sumround-presences,'multi_round_cluster_fraction':multi/len(groups),'compression':1-len(groups)/sumround})
        for card in outs:
            rd=card['round'];field=role[(run['case'],run['condition'])][card['agent']];us=units([card],eq,'equivalence');previous=set.union(*(roundids[q] for q in range(1,rd))) if rd>1 else set()
            contexts={'all':us,'new_outputs':[u for u in us if not retained(u,previous,adj)],'old_outputs':[u for u in us if retained(u,previous,adj)],'new_initial':[u for u in us if not retained(u,previous|initialids,adj)]}
            for scope,su in contexts.items():
                own=sum(weights(u['tags'],field,'fractional')[0] for u in su);other=sum(weights(u['tags'],field,'fractional')[1] for u in su)
                novel.append({'case':run['case'],'condition':run['condition'],'round':rd,'seat':card['agent'],'field':field,'scope':scope,'facts':len(su),'own_facts':own,'other_facts':other,'output_own':own/len(su) if su else None,'output_prime':(own-other)/len(su) if su else None,'share_of_all':len(su)/len(us)})
            shared=sum(sum(MAP[t]=='shared' for t in u['tags'])/len(u['tags']) for u in us)/len(us)
            profession=[]
            for u in us:
                ts=[t for t in u['tags'] if MAP[t] in FIELDS]
                if ts:profession.append(sum(MAP[t]==field for t in ts)/len(ts))
            domain.append({'case':run['case'],'condition':run['condition'],'round':rd,'field':field,'shared_mass':shared,'own_professional_only':avg(profession)})
    summaries=[]
    for cond in CONDS:
        rs=[r for r in repeat if r['condition']==cond];summaries.append({'condition':cond,**{k:stat([r[k] for r in rs]) for k in rs[0] if k not in ['case','condition']}})
    contrasts=[]
    for info,rd,field,scope,metric in itertools.product(['shared','split'],[1,2,3],FIELDS+['all'],['all','new_outputs','old_outputs','new_initial'],['output_own','output_prime','own_facts']):
        source=[r for r in novel if r['round']==rd and r['scope']==scope and (field=='all' or r['field']==field)]
        lookup=defaultdict(list)
        for r in source:lookup[(r['case'],r['condition'])].append(r[metric])
        diffs=[]
        for cid in sorted({r['case'] for r in source}):
            a=avg(lookup[(cid,info+'-specialist')]);b=avg(lookup[(cid,info+'-generic')]);diffs.append(a-b if a is not None and b is not None else None)
        contrasts.append({'info':info,'round':rd,'field':field,'scope':scope,'metric':metric,**stat(diffs)})
    interactions=[]
    # Paired difference of the specialist effect in new vs old facts, not comparison of separate CIs.
    for info,rd,metric in itertools.product(['shared','split'],[2,3],['output_own','output_prime']):
        ds=[]
        for cid in sorted({r['case'] for r in novel}):
            values={}
            for cond,scope in itertools.product([info+'-generic',info+'-specialist'],['new_outputs','old_outputs']):values[(cond,scope)]=avg([r[metric] for r in novel if r['case']==cid and r['condition']==cond and r['round']==rd and r['scope']==scope])
            if all(v is not None for v in values.values()):ds.append((values[(info+'-specialist','new_outputs')]-values[(info+'-generic','new_outputs')])-(values[(info+'-specialist','old_outputs')]-values[(info+'-generic','old_outputs')]))
        interactions.append({'info':info,'round':rd,'metric':metric,**stat(ds)})
    clinical=[]
    for cond,rd,field in itertools.product(CONDS,[1,2,3],FIELDS):
        rs=[r for r in O['profiles'] if r['condition']==cond and r['round']==rd and r['field']==field and r['unit']=='equivalence' and r['scheme']=='fractional' and r['match']=='equivalence']
        ds=[r for r in domain if r['condition']==cond and r['round']==rd and r['field']==field]
        clinical.append({'condition':cond,'round':rd,'field':field,'n_prime':sum(r['uptake_prime'] is not None for r in rs),'own_den_median':float(np.median([r['own_den'] for r in rs])),'other_den_median':float(np.median([r['other_den'] for r in rs])),'stable_prime':stat([r['uptake_prime'] for r in rs if r['own_den']>=3 and r['other_den']>=3]),'shared_mass':stat([r['shared_mass'] for r in ds]),'own_professional_only':stat([r['own_professional_only'] for r in ds])})
    social=json.loads((DEST/'social-uptake-observations.json').read_text());edges=[];factorial_edges=[]
    for r in social['edges']:
        if r['unit']!='equivalence' or r['scope']!='all' or r['match']!='equivalence':continue
        if r['label'] not in ['S','L','D']:continue
        e=dict(r,truth='Correct' if r['label'] in ['S','L'] else 'Incorrect',final='Correct' if r['final_label'] in ['S','L'] else 'Incorrect' if r['final_label']=='D' else 'Unclassified',status=r['status'].capitalize());factorial_edges.append(e)
        if e['final']!='Unclassified':edges.append(e)
    tests=[]
    for kind,receiver,outcome in itertools.product(['correctness','majority'],['self','peers'],['Correct','Incorrect']):
        es=[e for e in edges if e['final']==outcome and (e['seat']==e['target'])==(receiver=='self') and (kind=='correctness' or e['panel_kind']=='two_one')]
        test=paired_test(es,'truth' if kind=='correctness' else 'status','Correct' if kind=='correctness' else 'Minority','Incorrect' if kind=='correctness' else 'Majority')
        tests.append({'kind':kind,'receiver':receiver,'final':outcome,**test})
    valid=sorted([r for r in tests if r['p'] is not None],key=lambda r:r['p']);previous=1.
    for rank in range(len(valid),0,-1):r=valid[rank-1];previous=min(previous,r['p']*len(valid)/rank);r['q']=previous
    result={'repetition':summaries,'repetition_cases':repeat,'novel_profiles':novel,'novel_contrasts':contrasts,'novel_vs_old_interactions':interactions,'clinical_audit':clinical,'pooled_edges':edges,'factorial_edges':factorial_edges,'pooled_tests':tests,'policy':{'rounds':'pool R1→R2 and R2→R3; source rates, then panels, rounds, conditions and case means','novel':'output unit with no identity or direct equivalence to any previous-round output in this trace','q_family':'8 planned within-panel contrasts: 2 analyses × 2 receivers × 2 final outcomes','p':'two-sided case sign-flip, exact n<=16 else 100,000 draws; symmetry assumption'}}
    (DEST2/'revision-analysis.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False))
    print(json.dumps({'repetition':summaries,'novel_interactions':interactions,'tests':tests},indent=2))
if __name__=='__main__':main()
