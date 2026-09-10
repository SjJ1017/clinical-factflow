"""Check follow-up denominators, case clustering, alignment and plot coverage."""
import json
from collections import Counter,defaultdict
from followup import association,clustered
from analyze import DEST,CONDS,finite,avg

def main():
    # Repeated observations from one case do not increase that case's weight.
    assert clustered([{'case':'a','x':1}]*10+[{'case':'b','x':0}],'x')['mean']==.5
    toy=[{'case':'a','condition':'c','round':1,'label':'S','rate':.8},
         {'case':'a','condition':'c','round':1,'label':'D','rate':.2},
         {'case':'b','condition':'c','round':1,'label':'S','rate':0},
         {'case':'b','condition':'c','round':1,'label':'U','rate':1}]
    stat=association(toy,{'S'})
    assert stat['mixed_panels']==1 and stat['within_panel']['n']==1
    assert abs(stat['within_panel']['mean']-.6)<1e-12 and stat['excluded_turns']==1
    d=json.loads((DEST/'summary.json').read_text());f=d['followup']
    raw=json.loads((DEST/'followup-observations.json').read_text())
    groups=defaultdict(list)
    for p in f['points']:groups[tuple(p[k] for k in ['condition','round','unit','scheme','match'])].append(p)
    assert len(groups)==120 and all(len(v)==72 for v in groups.values())
    for key,ps in groups.items():
        assert len({(p['case'],p['seat']) for p in ps})==72
        assert Counter(p['field'] for p in ps)=={'clinical':24,'laboratory':24,'imaging':24}
        assert all(p['uptake_prime'] is None or -1<=p['uptake_prime']<=1 for p in ps)
        if key[1]>1:assert all(p['uptake_prime'] is not None for p in ps)
    for r in raw['source_uptake']:
        assert r['den']>0 and 0<=r['rate']<=1
        assert r['round'] in [1,2] and r['label'] in ['S','L','D','U','abstain']
    for r in raw['mismatch']+raw['condition_alignment']:
        assert r['seat']!=r['role_seat']
        assert 0<=r['information_distance']<=1 and 0<=r['role_distance']<=1
        assert abs(r['role_distance']-r['information_distance']-r['gap'])<1e-12
    expected=[]
    for r in f['associations']:
        if r['unit']=='equivalence' and r['match']=='equivalence' and r['scope']=='all' and r['grading']=='inclusive' and r['condition']=='all':
            expected.append((r['round'],r['receiver'],r['mixed_panels'],r['within_panel']['n']))
    assert sorted(expected)==[(1,'peers',42,15),(1,'self',42,15),(2,'peers',6,5),(2,'self',6,5)]
    result={'scatter_groups':len(groups),'points_per_group':72,'source_rates':len(raw['source_uptake']),'mismatch_alignments':len(raw['mismatch']),'condition_alignments':len(raw['condition_alignment']),'api_calls_added':0,'passed':True}
    (DEST/'followup-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
