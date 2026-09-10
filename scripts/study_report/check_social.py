"""Offline verification of outcome strata, majority membership and uptake risk sets."""
from social_uptake import contrast,stat,DEST,CONDS
import json,math

def main():
    assert stat([.2])['lo'] is None and stat([.2])['t_lo'] is None
    assert stat([])['mean'] is None
    toy=[{'case':'a','condition':'x','round':1,'group':'minority','value':.1},
         {'case':'a','condition':'x','round':1,'group':'majority','value':.2},
         {'case':'a','condition':'x','round':1,'group':'majority','value':.4}]
    result=contrast(toy,'group',{'minority'},{'majority'})
    assert abs(result['gap']['mean']+.2)<1e-12 and result['paired_cases']==1
    assert result['gap']['lo'] is None
    empty=contrast([toy[0]],'group',{'minority'},{'majority'})
    assert empty['gap']['mean'] is None and empty['paired_panels']==0
    D=json.loads((DEST/'summary.json').read_text());S=D['social_uptake'];O=json.loads((DEST/'social-uptake-observations.json').read_text())
    assert len(O['panels'])==240 and len(O['edges'])==17280
    assert len({(p['case'],p['condition'],p['round']) for p in O['panels']})==240
    for p in O['panels']:
        if p['kind']=='two_one':assert sorted(p['status'].values())==['majority','majority','minority']
    for e in O['edges']:
        assert 0<=e['num']<=e['den'] and 0<=e['new_num']<=e['new_den']<=e['den']
        if e['seat']==e['target']:assert e['new_den']==0
    for grade in ['same','inclusive']:
        for rd in [1,2]:
            rows={r['outcome']:r for r in S['inventory'] if r['grading']==grade and r['round']==rd}
            assert rows['all']['panels']==120
            assert sum(rows[k]['panels'] for k in ['correct','wrong','unresolved'])==120
    base={'unit':'equivalence','match':'equivalence','scope':'all','grading':'inclusive','condition':'all','measure':'peers'}
    pick=lambda rs,extra:next(r for r in rs if all(r.get(k)==v for k,v in (base|extra).items()))
    assert pick(S['associations'],{'round':1,'outcome':'wrong'})['paired_cases']==3
    assert pick(S['associations'],{'round':2,'outcome':'wrong'})['paired_cases']==0
    for rd in [1,2]:assert pick(S['majority'],{'round':rd,'outcome':'all','composition':'minority_correct'})['paired_cases']==0
    r=pick(S['majority'],{'round':2,'outcome':'all','composition':'all'})
    assert r['paired_panels']==21 and r['paired_cases']==13 and r['gap']['hi']<0 and r['gap']['t_hi']<0
    r=pick(S['associations'],{'round':1,'outcome':'wrong'})
    assert r['gap']['hi']<0<r['gap']['t_hi']
    for rd in [1,2]:
        old=next(r for r in D['followup']['associations'] if all(r.get(k)==v for k,v in (base|{'receiver':'peers','round':rd}).items() if k!='measure'))
        new=pick(S['associations'],{'round':rd,'outcome':'all'})
        assert abs(old['within_panel']['mean']-new['gap']['mean'])<1e-12
    # Answer-only results must not depend on fact units or professional filtering.
    groups={}
    for r in S['majority']:
        if not r['measure'].startswith('answer'):continue
        key=tuple(r[k] for k in ['round','grading','condition','measure','outcome','composition'])
        value=(r['gap']['mean'],r['paired_cases'])
        if key in groups:assert groups[key]==value
        groups[key]=value
    result={'passed':True,'panels':240,'edges':len(O['edges']),'source_values':len(O['sources']),'majority_panels_R1':36,'majority_panels_R2':21,'final_wrong_mixed_cases_R1':3,'final_wrong_mixed_cases_R2':0,'correct_minority_D_majority_panels':0,'api_calls_added':0}
    (DEST/'social-uptake-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
