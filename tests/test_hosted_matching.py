import json
from pathlib import Path
import numpy as np
import pytest
from clinical_factflow.config import load_config, RunConfig
from clinical_factflow.matching import HostedJudge, PairDecisions, match_mentions
from clinical_factflow.client import Client

ROOT = Path(__file__).resolve().parents[1]

def hosted():
    cfg=load_config(ROOT/'configs/demo-full.yaml')
    cfg.matching.backend='hosted'
    cfg.matching.hosted_model=cfg.generation.model_copy(update={'model':'deepseek-v4-flash'})
    cfg.matching.model='deepseek-v4-flash'
    cfg.matching.batch_size=2
    cfg.matching.max_parallel=2
    return cfg


def test_hosted_pair_ids_restore_order_and_threshold_is_not_qwen(tmp_path):
    class Fake:
        def __init__(self,*args):pass
        def request(self,messages,response_model,sample_id,validate):
            p=json.loads(messages[-1]['content'])['pairs']
            out=PairDecisions(pairs=[dict(pair_id=x['pair_id'],a_entails_b=True,b_entails_a=True,reason='test') for x in reversed(p)])
            validate(out)
            return out,{'sample_id':sample_id}
    cfg=hosted()
    judge=HostedJudge(cfg.matching,tmp_path,True,Fake)
    mentions=[{'id':str(i),'text':s} for i,s in enumerate(['Creatinine is 1 mg/dL.','The creatinine measurement is 1 mg/dL.'])]
    result=match_mentions(mentions,cfg.matching,lambda t:np.ones((len(t),2)),judge.score)
    assert len(result['facts'])==1
    assert result['relations'][0]['a_entails_b'] is True
    assert 'ab_margin' not in result['relations'][0]
    assert judge.metadata['local_margin_threshold_applied'] is False


def test_hosted_missing_ids_fail(tmp_path):
    class Missing:
        def __init__(self,*args):pass
        def request(self,messages,response_model,sample_id,validate):
            out=PairDecisions(pairs=[]);validate(out);return out,{}
    cfg=hosted()
    with pytest.raises(ValueError,match='every pair_id'):
        HostedJudge(cfg.matching,tmp_path,True,Missing).score([('a','b')])


def test_hosted_respects_remote_processing_and_model_identity(tmp_path):
    cfg=hosted()
    with pytest.raises(ValueError,match='disallows'):
        HostedJudge(cfg.matching,tmp_path,False)
    raw=cfg.model_dump();raw['matching']['model']='other'
    with pytest.raises(ValueError,match='must match'):
        RunConfig.model_validate(raw)


def test_http_client_sets_user_agent_and_audits_status_without_body(tmp_path,monkeypatch):
    import urllib.error
    cfg=hosted()
    cfg.generation.attempts=1
    monkeypatch.setenv(cfg.generation.api_key_env,'fake-test-key')
    def fail(req,timeout):
        assert req.get_header('User-agent')=='clinical-factflow/0.1'
        assert req.get_header('X-opencode-session').startswith('clinical-factflow-')
        raise urllib.error.HTTPError(req.full_url,403,'Forbidden',{},None)
    monkeypatch.setattr('urllib.request.urlopen',fail)
    from clinical_factflow.models import AgentAnswer
    with pytest.raises(RuntimeError):
        Client(cfg.generation,tmp_path,True).request([{'role':'system','content':'test'}],AgentAnswer,'test')
    audit=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert audit['http_status']==403
    assert 'fake-test-key' not in json.dumps(audit)
