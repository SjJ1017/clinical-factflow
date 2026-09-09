"""Rebuild the frozen pilot without network/model calls; requires pyarrow and PyYAML.
python scripts/medcase24/build.py --parquet /path/train.parquet --root .
The reviewed selection and source spans are fixed, not an automated diagnosis judge.
"""
from __future__ import annotations
import argparse, collections, copy, hashlib, itertools, json, re, statistics
from pathlib import Path
import pyarrow.parquet as pq
import yaml

SEED = 20260909
EXPECTED_SHA = '12b23b1d652caff931ea53012e8b84c2e74bfd3c6394c4fcdea63afa74158207'
SOURCE_URL = 'https://huggingface.co/datasets/zou-lab/MedCaseReasoning/resolve/469a536/data/train-00000-of-00001.parquet'
DOMAINS = {
 'cardiovascular':r'cardiac|myocard|coronary|ventric|atrium|atrial|aortic|echocardi|pericard|endocard|troponin',
 'respiratory':r'pulmon|lung|pleural|bronch|cough|dyspnea|hemoptysis|respiratory|pneumo',
 'neurologic':r'brain|cerebr|neurolog|seizure|headache|encephal|mening|ataxia|myoclon|spinal|paresis',
 'abdominal':r'hepatic|liver|biliary|pancrea|bowel|gastric|intestin|abdom|spleen|splen|colitis|diarrhea|jaundice',
 'renal_metabolic':r'renal|kidney|creatinine|proteinuria|hematuria|glomerul|nephro|thyroid|adrenal|cortisol|calcium|hypokal|hyperkal|hyponatr|hypernatr|acidosis',
 'systemic':r'lymphaden|lymph node|rash|arthralgia|arthritis|petech|purpur|pancytop|anemia|anaemia|bone marrow|eosinoph|skin|cutaneous|fever',
}
LAB = r'\b(?:laborator\w*|blood tests?|white (?:blood cell|cell)|wbc|hemoglobin|haemoglobin|platelet\w*|creatinine|urea|sodium|potassium|calcium|glucose|bilirubin|albumin|c-reactive|crp|esr|sedimentation|troponin|ferritin|ldh|lactate|antibod\w*|serolog\w*|cultures?|pcr|csf|cerebrospinal fluid|urinalysis|biops\w*|histolog\w*|immunohistochem\w*|cytolog\w*|bone marrow|cortisol|tsh)\b'
IMG = r'\b(?:ct|mri|mra|mrcp|pet|hrct|ultrasound|ultrasonograph\w*|sonograph\w*|radiograph\w*|x-ray|computed tomography|magnetic resonance|echocardiogra\w*|imaging|angiograph\w*|echogram)\b'
CATEGORIES = ('clinical', 'imaging', 'laboratory')
CONDITIONS = ('shared-generic','shared-specialist','split-generic','split-specialist','split-mismatched')
GENERIC = 'You are a physician participating in a case conference. Assess the available evidence, identify uncertainties and reconcile your assessment with received evidence.'
ROLES = {
 'clinical': ('Clinical assessment specialist', 'You are a physician specializing in clinical assessment. Focus on history, symptoms, bedside examination and temporal course; explain how these bear on the differential diagnosis and reconcile them with received evidence.'),
 'imaging': ('Imaging specialist', 'You are a physician specializing in imaging interpretation. Focus on anatomy, imaging patterns, distribution and temporal changes; explain how these bear on the differential diagnosis and reconcile them with received evidence.'),
 'laboratory': ('Laboratory and pathology specialist', 'You are a physician specializing in laboratory and pathology interpretation. Focus on specimen identity, measurements, tissue findings, thresholds and pertinent negatives; explain how these bear on the differential diagnosis and reconcile them with received evidence.'),
}
# Boundaries retain original whitespace and order; source units are NOT atomic facts.
def segments(text):
    bounds = [0] + [m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z“])|\n+', text)] + [len(text)]
    return [dict(index=i,start=a,end=b,text=text[a:b]) for i,(a,b) in enumerate(zip(bounds,bounds[1:])) if text[a:b].strip()]

def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()

def features(text):
    labs = set(x.lower() for x in re.findall(LAB,text,re.I)); images = re.findall(IMG,text,re.I)
    nums = len(re.findall(r'\b\d+(?:\.\d+)?\b',text))
    counts = {k:len(re.findall(p,text,re.I)) for k,p in DOMAINS.items()}
    return dict(words=len(text.split()),segments=len(segments(text)),lab_terms=len(labs),imaging_mentions=len(images),numbers=nums,
        domain_proxy=max(counts,key=counts.get),domain_scores=counts,
        complexity_proxy=min(len(labs),10)+min(nums,12)+min(len(images),5)+len(re.findall(r'\b(?:despite|however|but|negative|normal|persistent|recurrent|worsen\w*|repeat\w*)\b',text,re.I)))

def screen(rows):
    seen=set(); audit=[]
    for i,row in enumerate(rows):
        text=row['case_prompt']; f=features(text); norm=' '.join(text.casefold().split()); reasons=[]
        if not 210 <= f['words'] <= 550: reasons.append('word_range')
        if f['lab_terms'] < 4: reasons.append('few_lab_terms')
        if f['imaging_mentions'] < 2: reasons.append('few_imaging_mentions')
        if f['numbers'] < 5: reasons.append('few_measurements_proxy')
        if norm in seen: reasons.append('duplicate_prompt')
        if not row['final_diagnosis'] or not row['diagnostic_reasoning']: reasons.append('missing_reference')
        seen.add(norm)
        # Conservative opening-word heuristic, NOT a validated species classifier.
        if re.search(r'\b(?:cat|dog|canine|feline|equine|kitten|horse|bitch|stallion)\b',text[:260],re.I): reasons.append('animal_keyword_in_opening')
        gold=re.sub(r'[^a-z0-9 ]','',row['final_diagnosis'].casefold()).strip()
        direct=len(gold)>8 and gold in re.sub(r'[^a-z0-9 ]','',text.casefold())
        audit.append(dict(row_index=i,pmcid=row['pmcid'],**f,verbatim_answer_flag=direct,
            eligible=not reasons,exclusions=reasons,prompt_sha256=sha(text),random_rank=sha(f'{SEED}:{row["pmcid"]}')))
    return audit

def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def jsonl(path,items):
    path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in items))

def describe(values):
    values=sorted(values)
    return dict(min=values[0],median=statistics.median(values),max=values[-1])

class Dumper(yaml.SafeDumper):
    def ignore_aliases(self,data): return True

def build(parquet,root,base_config):
    raw_hash=hashlib.file_digest(parquet.open('rb'),'sha256').hexdigest()
    if raw_hash != EXPECTED_SHA: raise ValueError('Raw parquet checksum differs; do not reuse the frozen row IDs/span maps.')
    here=Path(__file__).parent
    specs=json.loads((here/'selection.json').read_text()); maps=json.loads((here/'partitions.json').read_text())
    rows=pq.read_table(parquet,columns=['pmcid','case_prompt','final_diagnosis','diagnostic_reasoning','article_link','journal','publication_date']).to_pylist()
    audit=screen(rows); eligible=[x for x in audit if x['eligible']]
    pool=[]
    for domain in DOMAINS:
        group=sorted([x for x in eligible if x['domain_proxy']==domain],key=lambda x:x['random_rank'])
        # Actual reviewed pool: 20 per proxy + 12 systemic and 8 abdominal alternates.
        pool += group[:32 if domain=='systemic' else 28 if domain=='abdominal' else 20]
    pool_ids={x['row_index'] for x in pool}
    assert len(pool_ids)==140
    chosen={x['row'] for x in specs}
    assert len(chosen)==24 and chosen <= pool_ids
    data=root/'data/medcasereasoning/pilot24'; cfgdir=root/'configs/pilots/medcase24'
    data.mkdir(parents=True,exist_ok=True); cfgdir.mkdir(parents=True,exist_ok=True)
    # Do not silently overwrite a live experiment definition.
    if any(cfgdir.glob('*.yaml')): raise FileExistsError('Pilot YAMLs already exist; rebuild into a separate root and compare.')
    jsonl(data/'screening.jsonl',audit)
    replacements={1427:'Thin imaging partition',8515:'Thin laboratory partition and clinical dominance',5999:'Thin imaging partition',5971:'Thin imaging partition'}
    ledger=[dict(**x,review_status='selected' if x['row_index'] in chosen else 'not_selected',
        decision_note='Included in the frozen diversity/partition pilot' if x['row_index'] in chosen else replacements.get(x['row_index'],'Not retained after qualitative partition, reference-support and diversity review; not a statement that this case is unusable')) for x in pool]
    jsonl(data/'review-ledger.jsonl',ledger)
    base=yaml.safe_load(base_config.read_text())
    assignments=list(itertools.permutations(CATEGORIES)); ids=['A','B','C']
    # Hash order determines balanced source seats; independent of outcome/diagnosis.
    seat_order=sorted(specs,key=lambda s:sha(f'{SEED}:seats:{s["pmcid"]}'))
    seats={s['row']:dict(zip(ids,assignments[j%6])) for j,s in enumerate(seat_order)}
    # Each source permutation receives both 3-cycle derangements twice.
    directions={s['row']:1+(j//6)%2 for j,s in enumerate(seat_order)}
    cases=[]; reviews=[]; runs=[]; source_profiles=[]
    for spec in specs:
        idx=spec['row']; row=rows[idx]; text=row['case_prompt']; mapping=maps[str(idx)]
        assert audit[idx]['eligible'] and spec['pmcid']==row['pmcid'] and sha(text)==spec['prompt_sha256']
        chunks=segments(text); indices={c['index'] for c in chunks}
        assert set(mapping['imaging']).isdisjoint(mapping['laboratory'])
        assert set(sum(mapping.values(),[])) <= indices
        evidence=[]
        for chunk in chunks:
            j=chunk['index']; category='imaging' if j in mapping['imaging'] else 'laboratory' if j in mapping['laboratory'] else 'clinical'
            chunk.update(category=category,mixed=j in mapping.get('mixed',[]),source_id=f'E{j:03d}')
            evidence.append(dict(id=chunk['source_id'],text=chunk['text'],category=category,source_field=f'case_prompt[{chunk["start"]}:{chunk["end"]}]'))
        assert ''.join(e['text'] for e in evidence)==text
        sizes={c:sum(len(e['text'].split()) for e in evidence if e['category']==c) for c in CATEGORIES}
        assert min(sizes.values()) >= 30, (idx,sizes)
        cid=f'mcr-train-{row["pmcid"]}'
        metadata=dict(dataset='zou-lab/MedCaseReasoning',revision='469a536',split='train',row_index=idx,pmcid=row['pmcid'],
            case_prompt_sha256=sha(text),partition_version='source-spans-v1')
        # References are handled by the runner's private evaluator channel, not prompts.
        cases.append(dict(id=cid,question='What is the most likely principal diagnosis for the current presentation?',evidence=evidence,
            reference=dict(final_diagnosis=row['final_diagnosis'],diagnostic_reasoning=row['diagnostic_reasoning']),metadata=metadata))
        opening=text[:160].lower()
        sex='female' if re.search(r'\b(woman|girl|female)\b',opening) else 'male' if re.search(r'\b(man|boy|male)\b',opening) else 'unparsed'
        age_match=re.search(r'(\d+)[- ](year|month)',opening)
        age=float(age_match[1])/(12 if age_match[2]=='month' else 1) if age_match else None
        rv=dict(**spec,id=cid,original=text,segments=chunks,words=len(text.split()),source_words=sizes,
            sex_reported=sex,age_years_parsed=age,source_to_seat=seats[idx],mismatch_direction=directions[idx],
            article_link=row['article_link'],dataset_link=f'https://huggingface.co/datasets/zou-lab/MedCaseReasoning/viewer/default/train?row={idx}',
            reference=cases[-1]['reference'],domain_proxy=audit[idx]['domain_proxy'],journal=row['journal'],publication_date=row['publication_date'])
        reviews.append(rv); source_profiles.append(sizes)
        for condition in CONDITIONS:
            cfg=copy.deepcopy(base); cfg['name']=f'mcr24-{row["pmcid"].lower()}-{condition}'; cfg['replicate']=0
            cfg['dataset'].update(adapter='canonical',path='../../../data/medcasereasoning/pilot24/cases.jsonl',case_ids=[cid],limit=1,selection_seed=SEED,evidence_dictionary=None)
            cfg['topology'].update(kind='full',schedule='synchronous',hub=None,order=ids,edges=[])
            cfg['context'].update(distribution='by_category' if condition.startswith('split') else 'shared',
                assignments={a:[seats[idx][a]] for a in ids} if condition.startswith('split') else {},
                evidence_visibility='every_round',self_memory='all',peer_memory='last')
            cfg['rounds']=3; cfg['max_parallel']=3
            cfg['outcome']=dict(method='majority',agent=None,scoring='ungraded')
            cfg['agents']=[]
            for j,agent in enumerate(ids):
                category=seats[idx][agent]
                if condition=='split-mismatched':category=CATEGORIES[(CATEGORIES.index(category)+directions[idx])%3]
                role,prompt=('Generic physician',GENERIC) if condition.endswith('generic') else ROLES[category]
                cfg['agents'].append(dict(id=agent,role=role,prompt=prompt,initial_context=''))
            filename=f'{cfg["name"]}.yaml'
            (cfgdir/filename).write_text('# Complete, frozen configuration: one case, one condition, one replicate.\n'+yaml.dump(cfg,Dumper=Dumper,sort_keys=False,allow_unicode=True,width=110))
            runs.append(dict(case_id=cid,condition=condition,config=str((cfgdir/filename).relative_to(root)),source_to_seat=seats[idx],role_by_seat={a['id']:a['role'] for a in cfg['agents']}))
    assert len({c['metadata']['pmcid'] for c in cases})==24
    jsonl(data/'cases.jsonl',cases); write_json(data/'review.json',reviews)
    # Interleave cases/conditions in a fixed hash shuffle; no execution here.
    run_order=sorted(runs,key=lambda r:sha(f'{SEED}:run-order:{r["config"]}'))
    write_json(data/'run-matrix.json',run_order)
    summary=dict(cohort_id='medcase24-v1',created='2026-09-09',source=dict(url=SOURCE_URL,revision='469a536',sha256=raw_hash,split='train',total_rows=len(rows)),
        network_or_model_calls_by_builder=0,eligible=len(eligible),reviewed=len(pool),selected=len(cases),configured_runs=len(runs),executed_runs=0,
        words=dict(train=describe([a['words'] for a in audit]),eligible=describe([a['words'] for a in eligible]),selected=describe([r['words'] for r in reviews])),
        stratum_counts=dict(collections.Counter(s['stratum'] for s in specs)),complexity_counts=dict(collections.Counter(s['complexity'] for s in specs)),
        mechanism_counts=dict(collections.Counter(s['mechanism'] for s in specs)),sex_counts=dict(collections.Counter(r['sex_reported'] for r in reviews)),
        pediatric_cases=sum(r['age_years_parsed'] is not None and r['age_years_parsed']<18 for r in reviews),
        source_words={c:describe([p[c] for p in source_profiles]) for c in CATEGORIES},
        mixed_source_units=sum(s['mixed'] for r in reviews for s in r['segments']),
        source_seat_permutation_counts=dict(collections.Counter('/'.join(seats[s['row']][a] for a in ids) for s in specs)),
        mismatch_direction_counts=dict(collections.Counter(directions.values())),
        conditions=list(CONDITIONS),generation_calls_if_executed_without_retries=len(runs)*9,
        statement='Purposive, evidence-rich feasibility cohort; no outcome-based screening, no empirically validated difficulty labels, no population accuracy estimate. Source units are not atomic facts.',
        input_manifest_sha256=sha((data/'cases.jsonl').read_text()),base_config_sha256=sha(base_config.read_text()),
        config_sha256={r['config']:sha((root/r['config']).read_text()) for r in run_order})
    write_json(data/'manifest.json',summary)
    template=(here/'review-template.html').read_text()
    payload=json.dumps(dict(summary=summary,cases=reviews),ensure_ascii=False).replace('<','\\u003c')
    (data/'review.html').write_text(template.replace('__PAYLOAD__',payload))
    print(json.dumps({k:summary[k] for k in ('eligible','reviewed','selected','configured_runs','words','source_words','sex_counts','pediatric_cases')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parquet',required=True,type=Path);p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--base-config',type=Path)
    a=p.parse_args();root=a.root.resolve();build(a.parquet,root,a.base_config or root/'configs/medcasereasoning-pilot.yaml')
