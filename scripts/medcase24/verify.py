"""Offline integrity checks for the prepared cohort and all 120 complete configs."""
from __future__ import annotations
import argparse, collections, copy, hashlib, json
from build import shared_metadata
from pathlib import Path
from clinical_factflow.config import load_config, differences
from clinical_factflow.datasets import allocate, load_cases
from clinical_factflow.runner import edges, messages_for


def check(root):
    data=root/'data/medcasereasoning/pilot24'
    manifest=json.loads((data/'manifest.json').read_text()); reviews=json.loads((data/'review.json').read_text())
    matrix=json.loads((data/'run-matrix.json').read_text()); by_case=collections.defaultdict(dict)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(data/'cases.jsonl')==manifest['input_manifest_sha256']
    assert len(matrix)==120 and len(reviews)==24
    for review in reviews:
        text=review['original']; chunks=review['segments']; cursor=0
        assert ''.join(s['text'] for s in chunks)==text
        for s in chunks:
            assert s['start']==cursor and text[s['start']:s['end']]==s['text'];cursor=s['end']
        assert cursor==len(text)
        assert min(review['source_words'].values())>=30
    review_by_id={r['id']:r for r in reviews}
    checks=0
    for row in matrix:
        path=root/row['config'];assert digest(path)==manifest['config_sha256'][row['config']]
        cfg=load_config(path); cases=load_cases(cfg.dataset);assert len(cases)==1
        case=cases[0]; assert case.id==row['case_id'];assert cfg.rounds==3
        by_case[case.id][row['condition']]=cfg.model_dump()
        expected_metadata=shared_metadata(case.id,review_by_id[case.id]['original'])
        assert all(a.initial_context==expected_metadata for a in cfg.agents)
        assert cfg.outcome.answer_field=='final_diagnosis'
        assert 'same patient' in cfg.task_prompt
        assert set(edges(cfg))=={(a,b) for a in 'ABC' for b in 'ABC' if a!=b}
        assert cfg.topology.schedule=='synchronous'
        assignment=allocate(case,cfg.agents,cfg.context);all_ids={s.id for s in case.evidence}
        if row['condition'].startswith('shared'):
            assert all(set(v)==all_ids for v in assignment.values())
        else:
            assert set().union(*map(set,assignment.values()))==all_ids
            assert sum(map(len,assignment.values()))==len(all_ids)
            assert all(assignment.values())
        source_ids={e.id:e.category for e in case.evidence}
        if row['condition']=='split-mismatched':
            roles={'clinical':'Clinical assessment specialist','imaging':'Imaging specialist','laboratory':'Laboratory and pathology specialist'}
            for agent in cfg.agents:
                category={source_ids[s] for s in assignment[agent.id]};assert len(category)==1
                assert agent.role != roles[next(iter(category))]
        # Changing metadata/reference alone must not change any agent message.
        hidden=case.model_copy(deep=True);hidden.reference={'answer':'REFERENCE_SENTINEL'};hidden.metadata={'rationale':'METADATA_SENTINEL'}
        turns=[]
        for rnd in (1,2,3):
            current=[]
            for agent in cfg.agents:
                msg,delivery=messages_for(cfg,case,agent,rnd,turns,assignment)
                assert msg==messages_for(cfg,hidden,agent,rnd,turns,assignment)[0]
                assert set(delivery['source_ids'])==set(assignment[agent.id])
                assert set(delivery['peer_turn_ids'])==({f'{a}|{rnd-1}' for a in 'ABC' if a!=agent.id} if rnd>1 else set())
                assert set(delivery['self_turn_ids'])=={f'{agent.id}|{r}' for r in range(1,rnd)}
                current.append(dict(id=f'{agent.id}|{rnd}',agent_id=agent.id,round=rnd,output_text=f'OFFLINE_SENTINEL_{agent.id}_{rnd}'))
                checks+=1
            turns+=current
    assert len(by_case)==24
    global_fixed=None
    for cid,arms in by_case.items():
        assert set(arms)==set(manifest['conditions'])
        pairs=[('shared-generic','split-generic',{'name','context.distribution','context.assignments'}),
               ('shared-generic','shared-specialist',{'name','agents'}),
               ('split-generic','split-specialist',{'name','agents'}),
               ('shared-specialist','split-specialist',{'name','context.distribution','context.assignments'}),
               ('split-specialist','split-mismatched',{'name','agents'})]
        for a,b,allowed in pairs:
            changes=differences(arms[a],arms[b]);assert all(any(p==v or p.startswith(v+'.') for v in allowed) for p in changes),(cid,a,b,changes)
        assert arms['shared-specialist']['agents']==arms['split-specialist']['agents']
        assert arms['shared-generic']['agents']==arms['split-generic']['agents']
        assert len({a['prompt'] for a in arms['shared-generic']['agents']})==1
        fixed=copy.deepcopy({k:v for k,v in arms['shared-generic'].items() if k not in {'name','dataset'}})
        for agent in fixed['agents']: agent['initial_context']='CASE_SPECIFIC_DEMOGRAPHICS'
        if global_fixed is None:global_fixed=fixed
        assert fixed==global_fixed
    assert set(manifest['source_seat_permutation_counts'].values())=={4}
    assert sorted(manifest['mismatch_direction_counts'].values())==[12,12]
    output=dict(status='passed',cases=24,configs=120,message_visibility_and_reference_isolation_checks=checks,
        verbatim_reconstruction=True,all_five_arms_have_identical_source_union=True,
        identical_shared_demographics_across_all_agents_and_arms=True,
        role_mismatch_has_zero_correctly_matched_seats=True,unexpected_config_differences=0,
        source_seat_permutations='6 permutations × 4 cases',mismatch_derangements='2 directions × 12 cases',network_calls=0,
        note='Offline structural validation; no claim of clinical reference validity or measured model performance.')
    (data/'validation.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));a=p.parse_args();check(a.root.resolve())
