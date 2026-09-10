"""Offline follow-up: clustered uptake associations and case-aligned mismatch."""
from analyze import *


def clustered(rows, value):
    groups=defaultdict(list)
    for r in rows: groups[r['case']].append(r.get(value))
    return summarize([avg(v) for v in groups.values()])


def association(rows, positive):
    good=[r for r in rows if r['label'] in positive]
    bad=[r for r in rows if r['label']=='D']
    # Equal weight to cases; two peers were already averaged within source turn.
    gs=clustered(good,'rate');bs=clustered(bad,'rate')
    cases=sorted({r['case'] for r in rows});gi={c:avg([r['rate'] for r in good if r['case']==c]) for c in cases};bi={c:avg([r['rate'] for r in bad if r['case']==c]) for c in cases}
    rng=np.random.default_rng(20260910);boot=[]
    for ix in rng.integers(0,len(cases),(2000,len(cases))):
        g=avg([gi[cases[i]] for i in ix]);b=avg([bi[cases[i]] for i in ix])
        if g is not None and b is not None:boot.append(g-b)
    gap={'mean':gs['mean']-bs['mean'] if gs['mean'] is not None and bs['mean'] is not None else None,'lo':float(np.quantile(boot,.025)) if boot else None,'hi':float(np.quantile(boot,.975)) if boot else None,'n':len(cases)}
    # Within identical case × condition × transition: only mixed-correctness panels.
    strata=defaultdict(list)
    for r in rows:strata[(r['case'],r['condition'],r['round'])].append(r)
    paired=[]
    for (case,cond,rd),rs in strata.items():
        g=avg([r['rate'] for r in rs if r['label'] in positive]);b=avg([r['rate'] for r in rs if r['label']=='D'])
        if g is not None and b is not None:paired.append({'case':case,'gap':g-b})
    return {'correct':gs,'wrong':bs,'gap':gap,'within_panel':clustered(paired,'gap'),'mixed_panels':len(paired),'correct_turns':len(good),'wrong_turns':len(bad),'excluded_turns':len(rows)-len(good)-len(bad)}


def extend(data):
    raw=json.loads((DEST/'observations.json').read_text());runs=load_runs()
    acc={(r['case'],r['condition'],r['round'],r['seat']):r for r in raw['accuracy'] if r['level']=='agent'}
    mappings={(r['case'],r['condition']):r['role_by_seat'] for r in raw['role_mapping']}
    source_rows=[];states={}
    for run in runs:
        case=run['case'];cond=run['condition'];cards={c['id']:c for c in run['cards']};eq=[];adjs={m:defaultdict(set) for m in ['equivalence','entailment']}
        for a,b,x,y in run['scores']:
            if x>=5.28:adjs['entailment'][a].add(b)
            if y>=5.28:adjs['entailment'][b].add(a)
            if x>=5.28 and y>=5.28:eq.append((a,b));adjs['equivalence'][a].add(b);adjs['equivalence'][b].add(a)
        for rd,seat in itertools.product([1,2,3],['A','B','C']):
            card=cards[f'{seat}|{rd}'];ids={f['id'] for f in card['facts']}
            for unit in ['equivalence','atoms']:
                us=units([card],eq,unit)
                for scheme in ['fractional','inclusive']:
                    states[(case,cond,rd,seat,unit,scheme)]={'distribution':entropy(us,scheme)['distribution'],'ids':ids}
                if rd==3:continue
                targets={s:cards[f'{s}|{rd+1}'] for s in ['A','B','C']}
                assert all(card['id'] in c['visible'] for c in targets.values())
                for match,adj in adjs.items():
                    for scope in ['all','professional']:
                        subset=us if scope=='all' else [u for u in us if any(MAP[t] in FIELDS for t in u['tags'])]
                        if not subset:continue
                        rates={s:sum(retained(u,{f['id'] for f in c['facts']},adj) for u in subset)/len(subset) for s,c in targets.items()}
                        for receiver in ['self','peers']:
                            rate=rates[seat] if receiver=='self' else avg([v for s,v in rates.items() if s!=seat])
                            source_rows.append({'case':case,'condition':cond,'round':rd,'seat':seat,'field':mappings[(case,cond)][seat],'unit':unit,'match':match,'scope':scope,'receiver':receiver,'label':acc[(case,cond,rd,seat)]['label'],'den':len(subset),'rate':rate})
    associations=[]
    for unit,match,scope,receiver,grading,cond,rd in itertools.product(['equivalence','atoms'],['equivalence','entailment'],['all','professional'],['self','peers'],['same','inclusive'],['all']+CONDS,[1,2]):
        rs=[r for r in source_rows if r['unit']==unit and r['match']==match and r['scope']==scope and r['receiver']==receiver and r['round']==rd and (cond=='all' or r['condition']==cond)]
        associations.append({'unit':unit,'match':match,'scope':scope,'receiver':receiver,'grading':grading,'condition':cond,'round':rd,**association(rs,{'S'} if grading=='same' else {'S','L'})})
    mismatch=[];condition_alignment=[]
    for case in sorted({r['case'] for r in runs}):
        base=mappings[(case,'split-specialist')];mis=mappings[(case,'split-mismatched')]
        for rd,seat,unit,scheme in itertools.product([1,2,3],['A','B','C'],['equivalence','atoms'],['fractional','inclusive']):
            role_seat=next(s for s in base if base[s]==mis[seat]);assert role_seat!=seat
            a=states[(case,'split-mismatched',rd,seat,unit,scheme)]
            gi=states[(case,'split-generic',rd,seat,unit,scheme)]
            sr=states[(case,'shared-specialist',rd,role_seat,unit,scheme)]
            b=states[(case,'split-specialist',rd,seat,unit,scheme)]
            c=states[(case,'split-specialist',rd,role_seat,unit,scheme)]
            tv=lambda x,y:sum(abs(x['distribution'][t]-y['distribution'][t]) for t in TAGS)/2
            jac=lambda x,y:1-len(x['ids']&y['ids'])/len(x['ids']|y['ids'])
            condition_alignment.append({'case':case,'round':rd,'seat':seat,'role_seat':role_seat,'unit':unit,'scheme':scheme,'information_distance':tv(a,gi),'role_distance':tv(a,sr),'gap':tv(a,sr)-tv(a,gi)})
            mismatch.append({'case':case,'round':rd,'seat':seat,'role_seat':role_seat,'field':mis[seat],'unit':unit,'scheme':scheme,'information_distance':tv(a,b),'role_distance':tv(a,c),'gap':tv(a,c)-tv(a,b),'atom_information_distance':jac(a,b),'atom_role_distance':jac(a,c),'atom_gap':jac(a,c)-jac(a,b)})
    msummary=[];csummary=[]
    for rd,unit,scheme in itertools.product([1,2,3],['equivalence','atoms'],['fractional','inclusive']):
        rs=[r for r in mismatch if r['round']==rd and r['unit']==unit and r['scheme']==scheme]
        cr=[r for r in condition_alignment if r['round']==rd and r['unit']==unit and r['scheme']==scheme]
        csummary.append({'round':rd,'unit':unit,'scheme':scheme,**{k:clustered(cr,k) for k in ['information_distance','role_distance','gap']}})
        msummary.append({'round':rd,'unit':unit,'scheme':scheme,**{k:clustered(rs,k) for k in ['information_distance','role_distance','gap','atom_information_distance','atom_role_distance','atom_gap']}})
    points=[{k:r[k] for k in ['case','condition','round','seat','field','unit','scheme','match','uptake_prime']} for r in raw['profiles']]
    dots=[]
    for cond,rd,unit,scheme,match in itertools.product(CONDS,[1,2,3],['equivalence','atoms'],['fractional','inclusive'],['equivalence','entailment']):
        rs=[r for r in points if r['condition']==cond and r['round']==rd and r['unit']==unit and r['scheme']==scheme and r['match']==match];assert len(rs)==72
        dots.append({'condition':cond,'round':rd,'unit':unit,'scheme':scheme,'match':match,'overall':clustered(rs,'uptake_prime'),'roles':{f:clustered([r for r in rs if r['field']==f],'uptake_prime') for f in FIELDS},'n':sum(r['uptake_prime'] is not None for r in rs),'missing':sum(r['uptake_prime'] is None for r in rs)})
    outcome=[]
    for case in sorted({r['case'] for r in runs}):
        rs=[r for r in raw['accuracy'] if r['case']==case and r['level']=='semantic_system' and r['round']==3]
        outcome.append({'case':case,'labels':{r['condition']:r['label'] for r in rs},'synonym_correct_conditions':sum(r['label']=='S' for r in rs),'compatible_conditions':sum(r['label'] in ['S','L'] for r in rs)})
    prime_alignment=[]
    for rd,unit,scheme,match in itertools.product([1,2,3],['equivalence','atoms'],['fractional','inclusive'],['equivalence','entailment']):
        ps=[r for r in raw['profiles'] if r['round']==rd and r['unit']==unit and r['scheme']==scheme and r['match']==match]
        rows=[]
        for case in sorted({r['case'] for r in ps}):
            values={c:[r['uptake_prime'] for r in ps if r['case']==case and r['condition']==c] for c in ['split-mismatched','split-generic','shared-specialist']}
            # Do not compare case means formed from different subsets of professions.
            if not all(len(v)==3 and all(finite(x) for x in v) for v in values.values()):continue
            a,b,c=[avg(values[k]) for k in ['split-mismatched','split-generic','shared-specialist']]
            rows.append({'case':case,'mismatch_mean':a,'information_mean':b,'role_mean':c,'information_distance':abs(a-b),'role_distance':abs(a-c),'gap':abs(a-c)-abs(a-b)})
        prime_alignment.append({'round':rd,'unit':unit,'scheme':scheme,'match':match,**{k:clustered(rows,k) for k in ['mismatch_mean','information_mean','role_mean','information_distance','role_distance','gap']}})
    extension={'prime_alignment':prime_alignment,'points':points,'dot_summary':dots,'associations':associations,'mismatch':msummary,'condition_alignment':csummary,'case_outcome':outcome}
    data['followup']=extension
    (DEST/'followup-observations.json').write_text(json.dumps({'source_uptake':source_rows,'mismatch':mismatch,'condition_alignment':condition_alignment},separators=(',',':'),allow_nan=False))
    (DEST/'summary.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False))
    print('Follow-up:',len(source_rows),'source rates;',len(mismatch),'aligned comparisons;',len(points),'scatter points across all controls',flush=True)
    return data

if __name__=='__main__':extend(json.loads((DEST/'summary.json').read_text()))
