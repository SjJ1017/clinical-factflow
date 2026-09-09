import io,json
import pytest
from clinical_factflow.client import Client
from clinical_factflow.config import Model
from clinical_factflow.models import Annotation,AgentAnswer

def annotation(domains):
    return Annotation(kind='observation',attribution='direct',certainty='asserted',polarity='affirmed',clinical_domain=domains)

def test_multilabel_domains_are_a_nonempty_set():
    assert annotation(['imaging','diagnosis']).clinical_domain==['diagnosis','imaging']
    for bad in ([],['imaging','imaging'],['other','history'],['cardiology'],'imaging'):
        with pytest.raises(ValueError):annotation(bad)
    with pytest.raises(ValueError):Annotation(**annotation(['history']).model_dump(),truth=True)

def test_anthropic_transport_preserves_usage_and_audits_truncation(tmp_path,monkeypatch):
    settings=Model(model='minimax-m2.5',api_format='anthropic',base_url='https://opencode.ai/zen/go/v1',api_key_env='TEST_API_KEY',temperature=0,max_tokens=8000,timeout_seconds=120,attempts=2)
    monkeypatch.setenv('TEST_API_KEY','synthetic-secret')
    usage={'input_tokens':10,'output_tokens':5,'cache_read_input_tokens':2,'cache_creation_input_tokens':3}
    response={'model':'minimax-m2.5','stop_reason':'end_turn','content':[{'type':'thinking','thinking':'not JSON'}, {'type':'text','text':'{"assessment":"a","answer":"b"}'}],'usage':usage}
    requests=[]
    def fake(req,timeout):
        requests.append(req)
        raw=response|({'stop_reason':'max_tokens'} if len(requests)==1 else {})
        return io.BytesIO(json.dumps(raw).encode())
    monkeypatch.setattr('urllib.request.urlopen',fake)
    value,info=Client(settings,tmp_path,True).request([{'role':'system','content':'extract'}, {'role':'user','content':'input'}],AgentAnswer,'case/output/A|1/extract')
    assert value.answer=='b' and info['usage']==usage
    assert len(requests)==2 and requests[0].full_url.endswith('/messages')
    req=requests[0]; payload=json.loads(req.data)
    assert payload['system'].startswith('extract') and all(m['role']!='system' for m in payload['messages'])
    assert req.get_header('X-api-key')=='synthetic-secret'
    assert requests[0].get_header('X-opencode-session')==requests[1].get_header('X-opencode-session')
    logs=[json.loads(p.read_text()) for p in tmp_path.glob('*.json')]
    assert sorted(x['status'] for x in logs)==['failed','ok']
    assert 'synthetic-secret' not in json.dumps(logs)
    assert all(x['response']['usage']==usage for x in logs)
