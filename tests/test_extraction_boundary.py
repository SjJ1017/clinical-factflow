import json
from clinical_factflow.config import load_config
from clinical_factflow.extraction import extract_record,records_for
from clinical_factflow.models import Atom,Extracted,SplitItem,SplitResult
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_both_passes_ignore_legacy_visible_input_and_gold():
    cfg=load_config(ROOT/'configs/demo-full.yaml').extraction
    cfg.atomize='all'
    seen=[]
    atom=Atom(text='Sodium is low.',quote='Sodium is low.',qualifiers=[],annotation=dict(kind='observation',attribution='direct',certainty='asserted',polarity='affirmed',clinical_domain=['laboratory']))
    class Capture:
        def request(self,messages,response_model,sample_id,validate=None):
            seen.append(messages)
            value=Extracted(facts=[atom]) if response_model is Extracted else SplitResult(facts=[SplitItem(parent_id='p0',parts=[atom])])
            if validate:validate(value)
            return value,{}
    result=extract_record(Capture(),cfg,{'id':'case/output/A|2','text':'Sodium is low.','reference_context':{'visible_input':'HIDDEN_PRIOR_TURN HIDDEN_SOURCE_REPORT','reference':'HIDDEN_GOLD'},'provenance':{'case_id':'case','channel':'output'}})
    assert len(result['mentions'])==1 and len(seen)==2
    assert set(json.loads(seen[0][-1]['content']))=={'text'}
    assert set(json.loads(seen[1][-1]['content']))=={'parents','original_text'}
    assert not any(w in json.dumps(seen) for w in ['HIDDEN_PRIOR_TURN','HIDDEN_SOURCE_REPORT','HIDDEN_GOLD','reference_context'])

def test_output_records_do_not_require_or_copy_generation_messages():
    cfg=load_config(ROOT/'configs/demo-full.yaml')
    case={'id':'case','question':'HIDDEN_TASK','evidence':[{'id':'E1','category':'laboratory','text':'Source text.'}]}
    trace={'cases':{'case':{'turns':[{'id':'A|2','output_text':'Only this output.','agent_id':'A','round':2}]}}}
    records=list(records_for(cfg,[case],trace));out=next(x for x in records if x['provenance']['channel']=='output')
    assert set(out)=={'id','text','provenance'}
    assert out['text']=='Only this output.' and 'HIDDEN_TASK' not in json.dumps(records)
