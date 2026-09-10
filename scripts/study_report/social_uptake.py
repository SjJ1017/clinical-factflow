"""Outcome-stratified and majority/minority uptake. Offline saved labels only."""
from analyze import *
from scipy.stats import t as student_t


def stat(values):
    s=summarize(values)
    s['t_lo']=s['t_hi']=None
    if s['n']<2:s['lo']=s['hi']=None
    else:
        a=np.asarray([x for x in values if finite(x)]);half=float(student_t.ppf(.975,len(a)-1)*a.std(ddof=1)/np.sqrt(len(a)))
        s['t_lo']=s['mean']-half;s['t_hi']=s['mean']+half
    return s


def contrast(rows, group, positive, negative):
    panels=defaultdict(list)
    for r in rows:panels[(r['case'],r['condition'],r['round'])].append(r)
    pairs=[];counts=Counter()
    for key,rs in panels.items():
        a=[r['value'] for r in rs if r[group] in positive and finite(r['value'])]
        b=[r['value'] for r in rs if r[group] in negative and finite(r['value'])]
        counts['positive_sources']+=len(a);counts['negative_sources']+=len(b)
        if a and b:pairs.append({'case':key[0],'condition':key[1],'round':key[2],'positive':avg(a),'negative':avg(b),'gap':avg(a)-avg(b)})
    bycase=defaultdict(list)
    for r in pairs:bycase[r['case']].append(r)
    result={k:stat([avg([r[k] for r in rs]) for rs in bycase.values()]) for k in ['positive','negative','gap']}
    result.update(counts);result.update(panels=len(panels),paired_panels=len(pairs),cases=len({r['case'] for r in rows}),paired_cases=len(bycase),eligible_sources=sum(finite(r['value']) for r in rows),missing_sources=sum(not finite(r['value']) for r in rows))
    result['known_receiver_values']=sum(r.get('receivers',0) for r in rows)
    result['missing_receiver_values']=sum(r.get('missing_receivers',0) for r in rows)
    result['case_gaps']=[{'case':case,'gap':avg([r['gap'] for r in rs]),'panels':len(rs)} for case,rs in bycase.items()]
    return result


def main():
    data=json.loads((DEST/'summary.json').read_text());runs=load_runs();labels={r['id']:r['label'] for r in data['judge_audit']}
    def relation(a,b):
        if not a or not b:return 'unknown'
        if norm(a)==norm(b):return 'S'
        return labels.get(pid(a,b),'unknown')
    agent={(r['case'],r['condition'],r['round'],r['seat']):r for r in data['raw_accuracy'] if r['level']=='agent'}
    final={(r['case'],r['condition']):r for r in data['raw_accuracy'] if r['level']=='semantic_system' and r['round']==3}
    panels=[];sources=[];edges=[]
    for run in runs:
        cid=run['case'];cond=run['condition'];cards={c['id']:c for c in run['cards']};eq=[];adj={m:defaultdict(set) for m in ['equivalence','entailment']}
        for a,b,x,y in run['scores']:
            if x>=5.28:adj['entailment'][a].add(b)
            if y>=5.28:adj['entailment'][b].add(a)
            if x>=5.28 and y>=5.28:eq.append((a,b));adj['equivalence'][a].add(b);adj['equivalence'][b].add(a)
        for rd in [1,2]:
            preds={s:agent[(cid,cond,rd,s)]['prediction'] for s in ['A','B','C']}
            rel={(a,b):relation(preds[a],preds[b]) for a,b in itertools.combinations(preds,2)};assert 'unknown' not in rel.values()
            same=[p for p,l in rel.items() if l=='S'];kind={0:'all_different',1:'two_one',2:'nontransitive',3:'unanimous'}[len(same)]
            status={s:('majority' if s in same[0] else 'minority') if kind=='two_one' else kind for s in preds}
            panel={'case':cid,'condition':cond,'round':rd,'kind':kind,'final_label':final[(cid,cond)]['label'],'source_labels':{s:agent[(cid,cond,rd,s)]['label'] for s in preds},'status':status}
            panels.append(panel)
            for seat in preds:
                card=cards[f'{seat}|{rd}'];base={'case':cid,'condition':cond,'round':rd,'seat':seat,'label':agent[(cid,cond,rd,seat)]['label'],'final_label':panel['final_label'],'status':status[seat],'panel_kind':kind}
                for unit in ['equivalence','atoms']:
                    us=units([card],eq,unit)
                    for scope in ['all','professional']:
                        su=us if scope=='all' else [u for u in us if any(MAP[t] in FIELDS for t in u['tags'])]
                        for match,links in adj.items():
                            er=[]
                            for target in preds:
                                out=cards[f'{target}|{rd+1}'];assert card['id'] in out['visible']
                                now={f['id'] for f in out['facts']};old={f['id'] for f in cards[f'{target}|{rd}']['facts']}
                                hits=[retained(u,now,links) for u in su];oldhits=[retained(u,old,links) for u in su]
                                newden=sum(not h for h in oldhits);newnum=sum(h and not o for h,o in zip(hits,oldhits))
                                nr=relation(preds[seat],out['diagnosis']);pr=relation(preds[seat],preds[target])
                                e={**base,'target':target,'unit':unit,'scope':scope,'match':match,'den':len(su),'num':sum(hits),'rate':avg(hits),'new_den':newden,'new_num':newnum,'new_rate':newnum/newden if newden else None,'prior_same_answer':pr=='S','next_answer_relation':nr,'answer_match':float(nr=='S') if nr!='unknown' else None}
                                er.append(e);edges.append(e)
                            for measure in ['self','peers','cross_opinion','new_to_peer','answer_self','answer_peers','answer_cross']:
                                chosen=[e for e in er if e['target']==seat] if measure in ['self','answer_self'] else [e for e in er if e['target']!=seat and (measure not in ['cross_opinion','answer_cross'] or not e['prior_same_answer'])]
                                key='new_rate' if measure=='new_to_peer' else 'answer_match' if measure.startswith('answer') else 'rate'
                                sources.append({**base,'unit':unit,'scope':scope,'match':match,'measure':measure,'value':avg([e[key] for e in chosen]),'receivers':sum(finite(e[key]) for e in chosen),'missing_receivers':sum(not finite(e[key]) for e in chosen)})
    summaries=[];majority=[];interactions=[]
    lookup=defaultdict(list)
    for r in sources:lookup[(r['unit'],r['scope'],r['match'],r['measure'],r['round'])].append(r)
    for unit,scope,match,measure,rd in lookup:
        rs0=lookup[(unit,scope,match,measure,rd)]
        for grading in ['inclusive','same']:
            correct={'S','L'} if grading=='inclusive' else {'S'}
            for condition in ['all']+CONDS:
                rs=[r for r in rs0 if condition=='all' or r['condition']==condition]
                identity={'unit':unit,'scope':scope,'match':match,'measure':measure,'round':rd,'grading':grading,'condition':condition}
                cs={}
                for outcome in ['all','correct','wrong']:
                    selected=[r for r in rs if outcome=='all' or (r['final_label'] in correct if outcome=='correct' else r['final_label']=='D')]
                    a=contrast(selected,'label',correct,{'D'});cs[outcome]=a
                    summaries.append({**identity,'outcome':outcome,**a})
                    two=[r for r in selected if r['panel_kind']=='two_one']
                    for composition in ['all','majority_correct','minority_correct']:
                        bypanel=defaultdict(list)
                        for r in two:bypanel[(r['case'],r['condition'],r['round'])].append(r)
                        eligible=[]
                        for rr in bypanel.values():
                            ma=[r['label'] for r in rr if r['status']=='majority'];mi=[r['label'] for r in rr if r['status']=='minority']
                            keep=composition=='all' or (all(x in correct for x in ma) and mi==['D'] if composition=='majority_correct' else all(x=='D' for x in ma) and len(mi)==1 and mi[0] in correct)
                            if keep:eligible+=rr
                        majority.append({**identity,'outcome':outcome,'composition':composition,**contrast(eligible,'status',{'minority'},{'majority'})})
                # Final-outcome moderation: joint resampling of cases, not separate CIs.
                ga={r['case']:r['gap'] for r in cs['correct']['case_gaps']};gb={r['case']:r['gap'] for r in cs['wrong']['case_gaps']};cases=sorted(ga.keys()|gb.keys());boot=[]
                if ga and gb:
                    for ix in np.random.default_rng(20260910).integers(0,len(cases),(2000,len(cases))):
                        a=avg([ga.get(cases[i]) for i in ix]);b=avg([gb.get(cases[i]) for i in ix])
                        if a is not None and b is not None:boot.append(a-b)
                enough=len(ga)>=2 and len(gb)>=2
                interactions.append({**identity,'mean':avg(list(ga.values()))-avg(list(gb.values())) if ga and gb else None,'lo':float(np.quantile(boot,.025)) if boot and enough else None,'hi':float(np.quantile(boot,.975)) if boot and enough else None,'correct_cases':len(ga),'wrong_cases':len(gb),'shared_cases':len(ga.keys()&gb.keys())})
    inventory=[]
    for grading in ['inclusive','same']:
        good={'S','L'} if grading=='inclusive' else {'S'}
        for rd in [1,2]:
            for outcome in ['all','correct','wrong','unresolved']:
                ps=[p for p in panels if p['round']==rd and (
                    outcome=='all' or
                    outcome=='correct' and p['final_label'] in good or
                    outcome=='wrong' and p['final_label']=='D' or
                    outcome=='unresolved' and p['final_label'] not in good|{'D'})]
                inventory.append({'grading':grading,'round':rd,'outcome':outcome,'panels':len(ps),'cases':len({p['case'] for p in ps}),'kinds':dict(Counter(p['kind'] for p in ps))})
    result={'associations':summaries,'majority':majority,'interactions':interactions,'inventory':inventory,'edge_count':len(edges),'source_rows':len(sources),'api_calls_added':0}
    data['social_uptake']=result
    (DEST/'social-uptake-observations.json').write_text(json.dumps({'panels':panels,'sources':sources,'edges':edges},separators=(',',':'),allow_nan=False))
    (DEST/'summary.json').write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False,allow_nan=False))
    print(json.dumps({'edges':len(edges),'sources':len(sources),'contrasts':len(summaries),'majority_contrasts':len(majority),'api_calls':0}),flush=True)

if __name__=='__main__':main()
