import json
from pathlib import Path
import pytest
from clinical_factflow.config import load_config
from clinical_factflow.extraction import atomization_reasons,extract_record
from clinical_factflow.models import Atom,Extracted,SplitResult,SplitItem

def atom(text,quote=None):
    return Atom(text=text,quote=quote or text,qualifiers=[],annotation=dict(kind='observation',attribution='direct',certainty='asserted',polarity='affirmed',clinical_domain=['history']))

@pytest.mark.parametrize('text',['The patient has fever and cough.','The patient has fever, cough.','Both knees are swollen.','These findings support pneumonia.','The patient is a 24-year-old woman.','The patient has no fever but cough persists.'])
def test_broad_candidate_rules_catch_known_failure_shapes(text):
    assert atomization_reasons(atom(text),text)

def test_candidate_is_not_a_split_decision():
    assert atomization_reasons(atom('The patient has head and neck cancer.'),'The patient has head and neck cancer.')
    assert atomization_reasons(atom('Sodium is 128 mmol/L.','sodium was low'),'Sodium is 128 mmol/L.')==['unlocated_quote']
    assert not atomization_reasons(atom('Sodium is 128 mmol/L.'),'Sodium is 128 mmol/L.')

def test_only_candidates_sent_while_order_and_skipped_atoms_stay_intact():
    cfg=load_config(Path(__file__).resolve().parents[1]/'configs/demo-full.yaml').extraction
    cfg.atomize='candidates_v1'
    parents=[atom('The patient has fever.'),atom('The patient has cough and pain.'),atom('The patient is male.')]
    seen=[]
    class Fake:
        def request(self,messages,response_model,sample_id,validate=None):
            payload=json.loads(messages[-1]['content']);seen.append(payload)
            value=Extracted(facts=parents) if response_model is Extracted else SplitResult(facts=[SplitItem(parent_id='p1',parts=[atom('The patient has cough.','cough and pain'),atom('The patient has pain.','cough and pain')])])
            if validate:validate(value)
            return value,{}
    result=extract_record(Fake(),cfg,{'id':'a','text':' '.join(p.text for p in parents),'provenance':{}})
    assert set(seen[1]['parents'])=={'p1'}
    assert [m['text'] for m in result['mentions']]==[parents[0].text,'The patient has cough.','The patient has pain.',parents[2].text]
    assert result['mentions'][0]['annotation']==parents[0].annotation.model_dump()
    assert result['atomization_selection']['selected']==1

def test_no_candidates_make_no_second_pass_call():
    cfg=load_config(Path(__file__).resolve().parents[1]/'configs/demo-full.yaml').extraction
    cfg.atomize='candidates_v1'
    class Fake:
        def request(self,messages,response_model,sample_id,validate=None):
            assert response_model is Extracted
            return Extracted(facts=[atom('The patient is male.')]),{}
    out=extract_record(Fake(),cfg,{'id':'a','text':'The patient is male.','provenance':{}})
    assert out['atomize_calls']==[] and out['atomization_selection']['selected']==0
