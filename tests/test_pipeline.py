from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from clinical_factflow.config import RunConfig, differences, load_config
from clinical_factflow.datasets import allocate, clinical, ddxplus, load_cases, medcase
from clinical_factflow.extraction import extract, extract_record, validate_splits
from clinical_factflow.matching import complete_link_groups, match_mentions, relation
from clinical_factflow.models import AgentAnswer, Atom, Extracted, SplitItem, SplitResult
from clinical_factflow.runner import messages_for, run, visible_turns
from clinical_factflow.client import Client
from clinical_factflow.io import verify_run

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg():
    return load_config(ROOT / "configs/demo-full.yaml")


class FakeClient:
    calls = []

    def __init__(self, *args):
        pass

    def request(self, messages, response_model, sample_id, validate=None):
        self.calls.append((sample_id,messages))
        value = AgentAnswer(assessment=f"Independent assessment for {sample_id}", answer="pneumonia")
        return value, {"messages":messages,"usage":{"prompt_tokens":7,"completion_tokens":3}}


def synthetic_atom(text, quote=None, polarity="affirmed", kind="observation"):
    return Atom(text=text, quote=quote or text, qualifiers=[], annotation={
        "kind":kind,"attribution":"direct","certainty":"asserted","polarity":polarity,
        "clinical_domain":"laboratory","attributed_to":None})


def test_topology_presets_only_change_topology(cfg):
    for topology in ("star","chain"):
        other = load_config(ROOT / f"configs/demo-{topology}.yaml")
        assert set(differences(cfg.model_dump(),other.model_dump())) <= {"name","topology.kind","topology.hub"}


def test_config_can_move_to_gpu_host_without_changing_fingerprint(cfg,tmp_path):
    p=tmp_path/"demo-full.yaml"
    p.write_text((ROOT/"configs/demo-full.yaml").read_text())
    moved=load_config(p)
    assert moved.model_dump()==cfg.model_dump()
    assert moved.dataset.resolve_path()!=cfg.dataset.resolve_path()


@pytest.mark.parametrize("name", [p.name for p in (ROOT/"configs").glob("*.yaml")])
def test_all_presets_validate(name):
    load_config(ROOT/"configs"/name)


def test_duplicate_yaml_key_rejected(tmp_path):
    p=tmp_path/"bad.yaml"; p.write_text("name: a\nname: b\n")
    with pytest.raises(ValueError,match="Duplicate YAML"):
        load_config(p)


def test_unknown_config_field_rejected(cfg):
    raw=cfg.model_dump(); raw["topology"]["prompts"]="accidental topology override"
    with pytest.raises(ValueError): RunConfig.model_validate(raw)


def test_unassigned_evidence_rejected(cfg):
    case=load_cases(cfg.dataset)[0]
    cfg.context.assignments["C"]=[]
    with pytest.raises(ValueError,match="Unassigned"): allocate(case,cfg.agents,cfg.context)


def test_sequential_cycle_rejected(cfg):
    raw=cfg.model_dump(); raw["topology"].update(kind="custom",schedule="sequential",edges=[["C","A"]])
    with pytest.raises(ValueError,match="must follow"): RunConfig.model_validate(raw)


def test_full_generation_visibility_independence_and_gold_exclusion(cfg,tmp_path):
    FakeClient.calls=[]
    out=run(cfg,tmp_path,FakeClient)
    trace=json.loads((out/"trace.json").read_text()); turns=next(iter(trace["cases"].values()))["turns"]
    assert len(turns)==9 and len(FakeClient.calls)==9
    assert len({t["output_text"] for t in turns[:3]})==3
    assert all(t["delivery"]["peer_turn_ids"]==[] for t in turns[:3])
    a2=next(t for t in turns if t["id"]=="A|2")
    assert a2["delivery"]["peer_turn_ids"]==["B|1","C|1"]
    assert a2["delivery"]["self_turn_ids"]==["A|1"]
    assert "Author-written fixture label" not in json.dumps([m for _,m in FakeClient.calls])
    assert "Final answer: pneumonia" not in turns[0]["messages"][-1]["content"]
    assert json.loads((out/"manifest.json").read_text())["status"]=="complete"
    verify_run(cfg,out)
    cfg.extraction.model.max_tokens+=1
    with pytest.raises(ValueError,match="YAML differs"): verify_run(cfg,out)


@pytest.mark.parametrize("schedule,expected",[("synchronous",["B|2"]),("sequential",["B|3"])])
def test_chain_timing(cfg,tmp_path,schedule,expected):
    cfg.topology.kind="chain"; cfg.topology.schedule=schedule
    out=run(cfg,tmp_path,FakeClient)
    turns=next(iter(json.loads((out/"trace.json").read_text())["cases"].values()))["turns"]
    assert turns[-1]["delivery"]["peer_turn_ids"]==expected
    b1=next(t for t in turns if t["id"]=="B|1")
    assert b1["delivery"]["peer_turn_ids"]==(["A|1"] if schedule=="sequential" else [])


def test_first_round_sources_and_memory_are_separate(cfg):
    case=load_cases(cfg.dataset)[0]; assignment=allocate(case,cfg.agents,cfg.context)
    cfg.context.evidence_visibility="first_round"; cfg.context.self_memory="none"
    msgs,delivery=messages_for(cfg,case,cfg.agents[0],2,[],assignment)
    assert not delivery["source_ids"] and not delivery["self_turn_ids"]
    assert case.evidence[0].text not in msgs[-1]["content"]


def test_failed_generation_is_not_a_complete_corpus(cfg,tmp_path):
    class Broken(FakeClient):
        def request(self,*args,**kwargs): raise RuntimeError("offline failure")
    with pytest.raises(RuntimeError): run(cfg,tmp_path,Broken)
    out=next(tmp_path.iterdir())
    assert json.loads((out/"manifest.json").read_text())["status"]=="failed"
    with pytest.raises(ValueError,match="incomplete"): extract(cfg,out,FakeClient)


def test_no_output_collisions(cfg,tmp_path):
    assert run(cfg,tmp_path,FakeClient) != run(cfg,tmp_path,FakeClient)


def test_clinical_gold_and_impressions_are_not_input(cfg):
    d=cfg.dataset.model_copy(update={"task":"final_diagnosis"})
    row={"id":1,"clinical_case_summary":"History. Auxiliary Examination duplicate lab.",
         "principal_diagnosis":"SECRET GOLD", "imageological_examination":{
             "CT":{"findings":"Opacity.","impression":"SECRET IMPRESSION"}},
         "laboratory_examination":{"panel":{"result":"Na 128 mmol/L","abnormal":"lossy"}}}
    case=clinical(row,d)
    inputs=json.dumps([e.model_dump() for e in case.evidence])
    assert "SECRET" not in inputs and "duplicate lab" not in inputs and "lossy" not in inputs
    assert "128 mmol/L" in inputs and case.reference["answer"]=="SECRET GOLD"
    d.task="imaging_diagnosis"; d.clinical_include_impressions=True
    with pytest.raises(ValueError,match="never its input"): clinical(row,d)


def test_clinical_missing_lab_schema_fails(cfg):
    row={"id":1,"clinical_case_summary":"History", "principal_diagnosis":"A",
         "laboratory_examination":{"panel":{"abnormal":"Na abnormal"}}}
    with pytest.raises(ValueError,match="missing findings"): clinical(row,cfg.dataset)


def test_medcase_does_not_feed_article_title_or_reasoning(cfg):
    row={"pmcid":"PMC1","case_prompt":"Lab Na 128 mmol/L.","final_diagnosis":"SECRET", "diagnostic_reasoning":"SECRET WHY", "title":"SECRET", "text":"SECRET ARTICLE"}
    c=medcase(row,cfg.dataset)
    assert all("SECRET" not in e.text for e in c.evidence)


def test_ddx_keeps_multichoice_units_and_hides_differential(cfg):
    row={"AGE":20,"SEX":"F","PATHOLOGY":"hidden","EVIDENCES":["E1_@_V1","E1_@_V2"],"DIFFERENTIAL_DIAGNOSIS":[["hidden",1.0]]}
    dictionary={"E1":{"question_en":"Pain location?","is_antecedent":False,"value_meaning":{"V1":{"en":"left arm"},"V2":{"en":"right arm"}}}}
    c=ddxplus(row,cfg.dataset,dictionary,0)
    assert len(c.evidence)==3
    assert "hidden" not in json.dumps([e.model_dump() for e in c.evidence])


def test_atomic_children_keep_annotations_and_overlapping_spans(cfg):
    text="No fever but pneumonia is possible."
    class SplitFake(FakeClient):
        def request(self,messages,response_model,sample_id,validate=None):
            if response_model is Extracted:
                value=Extracted(facts=[synthetic_atom(text)])
            else:
                value=SplitResult(facts=[SplitItem(parent_id="p0",parts=[
                    synthetic_atom("The patient has no fever.",text,"negated"),
                    synthetic_atom("The patient may have pneumonia.",text,kind="inference")])])
            if validate: validate(value)
            return value,{}
    record={"id":"a","text":text,"reference_context":{},"provenance":{"case_id":"c","channel":"output"}}
    result=extract_record(SplitFake(),cfg.extraction,record)
    assert len(result["mentions"])==2
    assert all(m["occurrences"][0]["spans"]==[[0,len(text)]] for m in result["mentions"])
    assert result["mentions"][0]["annotation"]["polarity"]=="negated"
    assert result["mentions"][1]["annotation"]["kind"]=="inference"


def test_partial_atomization_rejected():
    with pytest.raises(ValueError,match="exactly once"):
        validate_splits(SplitResult(facts=[]),["p0"])


def test_generation_to_extraction_artifact_contract(cfg,tmp_path):
    class FactClient(FakeClient):
        def request(self,messages,response_model,sample_id,validate=None):
            payload=json.loads(messages[-1]["content"])
            if response_model is Extracted:
                value=Extracted(facts=[synthetic_atom(payload["text"])])
            else:
                value=SplitResult(facts=[SplitItem(parent_id=k,parts=[Atom.model_validate(a)])
                                        for k,a in payload["parents"].items()])
            if validate:validate(value)
            return value,{"usage":{"prompt_tokens":1,"completion_tokens":1}}
    out=run(cfg,tmp_path,FakeClient)
    target=extract(cfg,out,FactClient)
    idx=json.loads((target/"index.json").read_text())
    assert idx["status"]=="complete" and len(idx["records"])==12
    assert all(json.loads((target/r["file"]).read_text())["mentions"] for r in idx["records"])
    with pytest.raises(FileExistsError):extract(cfg,out,FactClient)
    trace_path=out/"trace.json";trace_path.write_text(trace_path.read_text()+" ")
    with pytest.raises(ValueError,match="artifact changed"):extract(cfg,out,FactClient)


def test_directional_threshold_and_invalid_scores():
    assert relation(6,6,5.28)=="EQUIVALENT"
    assert relation(6,2,5.28)=="A_ENTAILS_B"
    assert relation(2,6,5.28)=="B_ENTAILS_A"
    assert relation(2,2,5.28)=="UNRELATED"
    with pytest.raises(ValueError): relation(float("nan"),1,5.28)


def test_no_transitive_false_equivalence():
    assert complete_link_groups(3,{(0,1):"EQUIVALENT",(1,2):"EQUIVALENT",(0,2):"UNRELATED"})==[[0,1],[2]]


def test_matching_preserves_all_mentions_and_blocker_decisions(cfg):
    mentions=[{"id":"1","text":"alpha"},{"id":"2","text":"alpha"},{"id":"3","text":"omega"}]
    def never(pairs): raise AssertionError("Blocker-rejected pair should not reach NLI")
    result=match_mentions(mentions,cfg.matching,lambda t:np.eye(2),never)
    assert result["blocker_rejected_count"]==1
    assert len(result["mention_to_fact"])==3
    assert result["mention_to_fact"]["1"]==result["mention_to_fact"]["2"]
    assert result["implicit_relation"]["decision_stage"]=="blocker"


def test_remote_data_gate(cfg,tmp_path):
    with pytest.raises(ValueError,match="disallows remote"):
        Client(cfg.extraction.model,tmp_path,False)


def test_http_empty_retry_and_private_audit(cfg,tmp_path,monkeypatch):
    # Real client path, mocked transport; verifies an empty result is not cached.
    monkeypatch.setenv(cfg.extraction.model.api_key_env,"test-key-must-not-be-written")
    results=[{"facts":[]},{"facts":[synthetic_atom("Na 128 mmol/L.").model_dump()]}]
    class Response:
        def __init__(self,value):self.value=value
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({"choices":[{"finish_reason":"stop","message":{"content":json.dumps(self.value)}}],"usage":{"prompt_tokens":9}}).encode()
    monkeypatch.setattr("urllib.request.urlopen",lambda *a,**k:Response(results.pop(0)))
    from clinical_factflow.extraction import require_facts
    c=Client(cfg.extraction.model,tmp_path,True)
    value,_=c.request([{"role":"system","content":"Extract"},{"role":"user","content":"Na"}],Extracted,"s",require_facts)
    logs=[p.read_text() for p in tmp_path.glob("*.json")]
    assert len(value.facts)==1 and len(logs)==2
    assert "test-key-must-not-be-written" not in "".join(logs)
    assert {json.loads(x)["status"] for x in logs}=={"ok","failed"}


def test_final_diagnosis_voting_ignores_explanatory_answer_strings(cfg, tmp_path):
    from clinical_factflow.models import DiagnosticAnswer
    cfg.outcome.answer_field = "final_diagnosis"
    class DiagnosisClient(FakeClient):
        def request(self, messages, response_model, sample_id, validate=None):
            assert response_model is DiagnosticAnswer
            value = DiagnosticAnswer(assessment="Provisional interpretation.",
                answer=f"Different free-text conclusion for {sample_id}", final_diagnosis="Pneumonia")
            return value, {"messages": messages}
    out = run(cfg, tmp_path, DiagnosisClient)
    case = next(iter(json.loads((out / "trace.json").read_text())["cases"].values()))
    assert len({t["answer"] for t in case["turns"][-3:]}) == 3
    assert len(case["round_outcomes"]) == 3
    assert all(o["answer"] == "pneumonia" and not o["tie_abstention"] for o in case["round_outcomes"])
    assert all(t["output_text"].endswith("Final diagnosis: Pneumonia") for t in case["turns"])
    assert "Final diagnosis: Pneumonia" in case["turns"][3]["messages"][-1]["content"]
    verify_run(cfg, out)


def test_round_scoring_ties_and_no_final_field_fallback(cfg):
    from clinical_factflow.runner import outcome
    cfg.outcome.answer_field = "final_diagnosis"
    cfg.outcome.scoring = "exact"
    case = load_cases(cfg.dataset)[0]
    case.reference = {"accepted_answers": ["Pneumonia"]}
    turns = [dict(agent_id=a, round=r, answer="Pneumonia", final_diagnosis=d)
             for r, diagnoses in [(1, ["Pneumonia", "Asthma", "Bronchitis"]),
                                  (2, [" Pneumonia. ", "pneumonia", "Asthma"])]
             for a, d in zip("ABC", diagnoses)]
    first, second = (outcome(cfg, case, turns, r) for r in (1, 2))
    assert first["tie_abstention"] and first["correct"] is False
    assert sum(a["correct"] for a in first["agent_results"]) == 1
    assert second["correct"] and sum(a["correct"] for a in second["agent_results"]) == 2
    with pytest.raises(ValueError, match="exactly one"):
        outcome(cfg, case, turns[:-1], 2)
    del turns[0]["final_diagnosis"]
    with pytest.raises(KeyError): outcome(cfg, case, turns, 1)


def test_final_diagnosis_is_required_and_single_line():
    from clinical_factflow.models import DiagnosticAnswer
    for final in ("", "   ", "Pneumonia\nAsthma"):
        with pytest.raises(ValueError):
            DiagnosticAnswer(assessment="Uncertain", answer="Provisional", final_diagnosis=final)
    with pytest.raises(ValueError): DiagnosticAnswer(assessment="Uncertain", answer="Provisional")


def test_pilot_shared_metadata_has_only_identity_age_and_reported_sex(cfg):
    import importlib.util
    spec = importlib.util.spec_from_file_location("pilot_builder", ROOT / "scripts/medcase24/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for opening, age in [("A 71‐year‐old man has SECRET COMPLAINT.", "71 years"),
                         ("An 18-month-old boy has SECRET COMPLAINT.", "18 months")]:
        common = module.shared_metadata("synthetic-id", opening)
        assert len(common.splitlines()) == 3 and f"Age: {age}" in common
        assert "SECRET" not in common and "synthetic-id" not in common
        for a in cfg.agents: a.initial_context = common
        case = load_cases(cfg.dataset)[0]
        assignment = allocate(case, cfg.agents, cfg.context)
        for a in cfg.agents:
            msg, delivery = messages_for(cfg, case, a, 1, [], assignment)
            assert common in msg[-1]["content"]
            assert delivery["initial_context_id"] == f"initial:{a.id}"
    with pytest.raises(ValueError): module.shared_metadata("case", "Patient with no demographics.")
