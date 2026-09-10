"""Apply explicit local review decisions, preserving original model responses."""
import json
from judge_names import OUT,pid

def main():
    original=json.loads((OUT/'results.json').read_text())
    pairs=json.loads((OUT/'config.json').read_text())['pairs']
    decisions=json.loads((OUT/'review-decisions.json').read_text())
    labels=dict(original['labels']);seen=set()
    for row in decisions['corrections']:
        key=row['id']
        assert key not in seen and pid(*row['names'])==key
        assert row['names']==pairs[key] and row['original']==original['labels'][key]
        assert row['reviewed'] in ['S','L','D','U'] and row['note']
        seen.add(key);labels[key]=row['reviewed']
    result={'complete':True,'scope':decisions['scope'],'corrections':decisions['corrections'],'labels':labels}
    (OUT/'review.json').write_text(json.dumps(result,indent=2))
    print('Applied explicit local corrections / flags:',len(seen))

if __name__=='__main__':main()
