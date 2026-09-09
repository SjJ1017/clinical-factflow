import json, threading, time
from pathlib import Path
import pytest
from clinical_factflow.config import load_config
from clinical_factflow.models import Atom, Extracted, SplitResult, SplitItem
from clinical_factflow.extraction import extract_record
from clinical_factflow.resumable_extraction import CheckpointClient, Paused, sealed_read, sealed_write, execute

ROOT=Path(__file__).resolve().parents[1]
def cfg():return load_config(ROOT/'configs/demo-full.yaml').extraction
def fact(text):
 return Atom(text=text,quote=text,qualifiers=[],annotation=dict(kind='observation',attribution='direct',certainty='asserted',polarity='affirmed',clinical_domain=['history']))

def test_pause_after_extraction_resumes_only_atomization(tmp_path):
 setting=cfg();stop=threading.Event();calls=[]
 class Fake:
  def __init__(self,*a):pass
  def request(self,messages,response_model,sample_id,validate=None):
   calls.append(sample_id)
   if response_model is Extracted:
    value=Extracted(facts=[fact('Fever and cough.')]);stop.set()
   else:value=SplitResult(facts=[SplitItem(parent_id='p0',parts=[fact('Fever.'),fact('Cough.')])])
   if validate:validate(value)
   return value,{'call_id':str(len(calls))}
 record={'id':'runA/output/A|1','text':'Fever and cough.','provenance':{}}
 with pytest.raises(Paused):extract_record(CheckpointClient(setting.model,tmp_path,True,stop,time.time()+60,Fake),setting,record)
 stop.clear()
 out=extract_record(CheckpointClient(setting.model,tmp_path,True,stop,time.time()+60,Fake),setting,record)
 assert calls==['runA/output/A|1/extract','runA/output/A|1/atomize/0']
 assert len(out['mentions'])==2

def test_completed_queue_resume_has_zero_model_calls(tmp_path):
 setting=cfg();calls=[]
 class Fake:
  def __init__(self,*a):pass
  def request(self,messages,response_model,sample_id,validate=None):
   calls.append(sample_id);value=Extracted(facts=[fact('The patient is male.')])
   if validate:validate(value)
   return value,{}
 tasks=[{'id':'one','record':{'id':'run/one','text':'The patient is male.','provenance':{}},'bindings':[]}]
 first=execute(tasks,setting,tmp_path,time.time()+60,threading.Event(),Fake)
 second=execute(tasks,setting,tmp_path,time.time()+60,threading.Event(),Fake)
 assert first['completed']==second['completed']==1 and len(calls)==1

def test_corrupt_checkpoint_fails_closed(tmp_path):
 p=tmp_path/'x.json';sealed_write(p,{'x':1});obj=json.loads(p.read_text());obj['value']['x']=2;p.write_text(json.dumps(obj))
 with pytest.raises(ValueError,match='integrity'):sealed_read(p)

def test_changed_sample_or_prompt_cannot_reuse_request(tmp_path):
 setting=cfg();calls=[]
 class Fake:
  def __init__(self,*a):pass
  def request(self,messages,response_model,sample_id,validate=None):
   calls.append(sample_id);return Extracted(facts=[fact('The patient is male.')]),{}
 c=CheckpointClient(setting.model,tmp_path,True,threading.Event(),time.time()+60,Fake)
 messages=[{'role':'system','content':'Extract.'},{'role':'user','content':'text'}]
 c.request(messages,Extracted,'runA');c.request(messages,Extracted,'runA');c.request(messages,Extracted,'runB')
 c.request([{'role':'system','content':'New prompt.'},messages[1]],Extracted,'runA')
 assert len(calls)==3

def test_successful_raw_response_recovered_after_checkpoint_interruption(tmp_path):
 setting=cfg();messages=[{'role':'system','content':'Extract.'},{'role':'user','content':'text'}];value=Extracted(facts=[fact('The patient is male.')]);system=messages[0]['content']+'\nReturn one JSON object matching this schema. No markdown.\n'+json.dumps(Extracted.model_json_schema(),ensure_ascii=False)
 (tmp_path/'calls').mkdir();(tmp_path/'calls'/'raw.json').write_text(json.dumps({'status':'ok','sample_id':'task','call_id':'raw','request':{'model':setting.model.model,'system':system,'messages':[messages[1]]},'response':{'model':setting.model.model,'content':[{'type':'text','text':value.model_dump_json()}]},'wall_seconds':1}))
 class Never:
  def __init__(self,*a):pass
  def request(self,*a,**kw):raise AssertionError('Must recover without a model call')
 got,info=CheckpointClient(setting.model,tmp_path,True,threading.Event(),time.time()+60,Never).request(messages,Extracted,'task')
 assert got==value and info['call_id']=='raw'
