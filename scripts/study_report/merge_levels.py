"""Case-paired cross-round coalescence and direct-recurrence audit, offline."""
from analyze import *
from analyze_figure_revision import stat
OUT=ROOT/'findings/medcase24-merging'

def metrics(run,threshold=5.28):
    eq=[(a,b) for a,b,x,y in run['scores'] if min(x,y)>=threshold]
    ids={rd:{f['id'] for c in run['cards'] if c['channel']=='output' and c['round']==rd for f in c['facts']} for rd in [1,2,3]}
    groups={rd:components(ids[rd],eq) for rd in ids};allids=set.union(*ids.values());full=components(allids,eq)
    s=sum(len(g) for g in groups.values());presence=sum(sum(bool(g&ids[rd]) for rd in ids) for g in full)
    result={'case':run['case'],'condition':run['condition'],'threshold':threshold,'round_sum':s,'trace_facts':len(full),'compression':1-len(full)/s,'repeat_share':(presence-len(full))/s,'bridge_share':(s-presence)/s,'rounds_per_cluster':presence/len(full),'unique_atoms':len(allids)}
    rounds=[]
    for ra,rb in [(1,2),(1,3),(2,3)]:
        ga,gb=groups[ra],groups[rb];ma={x:i for i,g in enumerate(ga) for x in g};mb={x:i for i,g in enumerate(gb) for x in g}
        direct={(x,x) for x in ids[ra]&ids[rb]}
        for a,b in eq:
            if a in ma and b in mb:direct.add((a,b))
            if b in ma and a in mb:direct.add((b,a))
        pairs={(ma[a],mb[b]) for a,b in direct}
        da={a for a,b in direct};db={b for a,b in direct}
        ca={a for a,b in pairs};cb={b for a,b in pairs}
        rounds.append({'from_round':ra,'to_round':rb,'direct_coverage':.5*(len(ca)/len(ga)+len(cb)/len(gb)),'raw_direct_coverage':.5*(len(da)/len(ids[ra])+len(db)/len(ids[rb])),'direct_pair_density':len(pairs)/(len(ga)*len(gb)),'raw_pair_density':len(direct)/(len(ids[ra])*len(ids[rb])),'prior_retained':len(ca)/len(ga),'later_repeated':len(cb)/len(gb),'pairs':len(pairs),'possible_pairs':len(ga)*len(gb)})
    for key in ['direct_coverage','raw_direct_coverage','direct_pair_density','raw_pair_density']:result[key]=avg([r[key] for r in rounds])
    result['round_pairs']=rounds
    return result

def paired(rows,left,right,key):
    d={(r['case'],r['condition']):r[key] for r in rows};cases=sorted({r['case'] for r in rows});values=[d[c,left]-d[c,right] for c in cases]
    a=np.asarray(values);signs=np.random.default_rng(20260912).choice([-1,1],size=(100000,len(a)));p=float((1+(abs((signs*a).mean(axis=1))>=abs(a.mean())-1e-12).sum())/100001)
    return {'left':left,'right':right,'metric':key,**stat(values),'p':p,'case_differences':dict(zip(cases,values))}

def main():
    OUT.mkdir(parents=True,exist_ok=True);runs=load_runs();rows=[metrics(r) for r in runs]
    keys=['compression','repeat_share','bridge_share','direct_coverage','raw_direct_coverage','direct_pair_density','raw_pair_density','rounds_per_cluster','round_sum','trace_facts']
    summaries=[{'condition':c,**{k:stat([r[k] for r in rows if r['condition']==c]) for k in keys}} for c in CONDS]
    contrasts=[paired(rows,a,b,k) for a,b in [('shared-generic','split-generic'),('shared-specialist','split-specialist'),('split-mismatched','split-specialist'),('shared-specialist','shared-generic'),('split-specialist','split-generic')] for k in keys]
    # Six exploratory contrasts for the newly proposed metric family; other audits descriptive.
    family=[x for x in contrasts if x['left'].startswith('shared') and x['right'].startswith('split') and x['metric'] in ['compression','direct_coverage','raw_direct_coverage']]
    ordered=sorted(family,key=lambda x:x['p']);q=1
    for rank in range(len(ordered),0,-1):
        x=ordered[rank-1];q=min(q,x['p']*len(ordered)/rank);x['q']=q
    sensitivity=[]
    for threshold in [4.5,5.,5.5,6.]:
        rs=[metrics(r,threshold) for r in runs]
        for role in ['generic','specialist']:
            for key in ['compression','direct_coverage']:
                sensitivity.append({'threshold':threshold,**paired(rs,'shared-'+role,'split-'+role,key)})
    pairs=[{'condition':c,'from_round':ra,'to_round':rb,**{k:stat([p[k] for r in rows if r['condition']==c for p in r['round_pairs'] if p['from_round']==ra and p['to_round']==rb]) for k in ['direct_coverage','raw_direct_coverage','prior_retained','later_repeated','direct_pair_density']}} for c, (ra,rb) in itertools.product(CONDS,[(1,2),(1,3),(2,3)])]
    result={'definitions':{'compression':'1 - pooled output equivalence components / sum of separate-round components','direct_coverage':'mean over the 3 round pairs of half the sum of each side\'s fraction of within-round units with an identity or direct equivalence link to the other round; no cross-round closure','raw_direct_coverage':'same coverage on unique atom IDs without any clustering','repeat_share':'(global cluster-round presences - global components) / sum of round components','bridge_share':'(sum of round components - global cluster-round presences) / sum of round components'},'cases':rows,'conditions':summaries,'contrasts':contrasts,'round_pairs':pairs,'threshold_sensitivity':sensitivity,'method':{'independent_cases':24,'bootstrap':2000,'sign_flip_draws':100000,'q_family':'6 exploratory comparisons: shared-split within generic/specialist for compression, unit direct coverage, raw atom direct coverage','matching':'all saved scores, blocker negatives remain unrelated, no API calls'}}
    for r in rows:assert abs(r['compression']-r['repeat_share']-r['bridge_share'])<1e-12
    (OUT/'analysis.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False))
    for s in summaries:print(s['condition'],{k:round(s[k]['mean'],4) for k in ['compression','repeat_share','bridge_share','direct_coverage','raw_direct_coverage']})
    for x in family:print('DIFF',x['left'],x['metric'],{k:x[k] for k in ['mean','lo','hi','p','q']})
if __name__=='__main__':main()
