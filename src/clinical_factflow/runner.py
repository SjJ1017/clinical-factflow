from __future__ import annotations

import json
import platform
import re
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from .client import Client
from .config import digest
from .datasets import allocate, load_cases
from .io import atomic_json, code_snapshot, file_hash
from .models import AgentAnswer, DiagnosticAnswer


def edges(cfg):
    t, ids = cfg.topology, cfg.topology.order
    if t.kind == "full":
        return [(a,b) for a in ids for b in ids if a != b]
    if t.kind == "star":
        return [(a,b) for a in ids for b in ids if a != b and t.hub in (a,b)]
    if t.kind == "chain":
        return list(zip(ids, ids[1:]))
    return t.edges if t.kind == "custom" else []


def visible_turns(cfg, agent, round_, turns):
    predecessors = {a for a,b in edges(cfg) if b == agent}
    own = [t for t in turns if t["agent_id"] == agent and t["round"] < round_]
    if cfg.context.self_memory == "none":
        own = []
    elif cfg.context.self_memory == "last":
        own = own[-1:]
    target_round = round_ if cfg.topology.schedule == "sequential" else round_ - 1
    peer = [t for t in turns if t["agent_id"] in predecessors and t["round"] <= target_round]
    if cfg.context.peer_memory == "last":
        # Fresh round only. A missing predecessor is an error, never an older fallback.
        peer = [t for t in peer if t["round"] == target_round]
    return own, peer


def messages_for(cfg, case, agent, round_, turns, assignment):
    own, peer = visible_turns(cfg, agent.id, round_, turns)
    source_ids = assignment[agent.id] if round_ == 1 or cfg.context.evidence_visibility == "every_round" else []
    sources = [e for e in case.evidence if e.id in source_ids]
    sections = [f"Task:\n{case.question}", f"Round: {round_}/{cfg.rounds}"]
    if agent.initial_context:
        sections.append("Initial context:\n" + agent.initial_context)
    if sources:
        sections.append("Case evidence:\n" + "\n\n".join(f"[{e.id}]\n{e.text}" for e in sources))
    if own:
        sections.append("Your previous outputs:\n" + "\n\n".join(f"[{t['id']}]\n{t['output_text']}" for t in own))
    if peer:
        sections.append("Received peer outputs:\n" + "\n\n".join(f"[{t['id']}]\n{t['output_text']}" for t in peer))
    return [{"role": "system", "content": cfg.task_prompt + "\n\n" + agent.prompt},
            {"role": "user", "content": "\n\n".join(sections)}], {
                "source_ids": source_ids, "self_turn_ids": [t["id"] for t in own],
                "peer_turn_ids": [t["id"] for t in peer],
                "initial_context_id": f"initial:{agent.id}" if agent.initial_context else None,
            }


def normalized(answer):
    return " ".join(str(answer).casefold().split()).rstrip(".")


def outcome(cfg, case, turns, round_=None):
    round_ = cfg.rounds if round_ is None else round_
    last = [t for t in turns if t["round"] == round_]
    if {t["agent_id"] for t in last} != set(cfg.topology.order) or len(last) != len(cfg.agents):
        raise ValueError("A round outcome requires exactly one output from every agent")
    field = cfg.outcome.answer_field
    if cfg.outcome.method == "agent":
        answer = next(t[field] for t in last if t["agent_id"] == cfg.outcome.agent)
        tied = False
    else:
        counts = Counter(normalized(t[field]) for t in last)
        top = counts.most_common()
        tied = len(top) > 1 and top[0][1] == top[1][1]
        answer = None if tied else top[0][0]
    correct = None
    accepted_normalized = None
    if cfg.outcome.scoring == "exact":
        accepted = case.reference.get("accepted_answers")
        if not accepted or not all(isinstance(x, str) and x.strip() for x in accepted):
            raise ValueError("Exact scoring requires explicit accepted_answers, never arbitrary free-text diagnosis matching")
        accepted_normalized = {normalized(x) for x in accepted}
        correct = answer is not None and normalized(answer) in accepted_normalized
    agent_results = [{"agent_id": t["agent_id"], "answer": t[field],
                      "correct": None if accepted_normalized is None else normalized(t[field]) in accepted_normalized}
                     for t in last]
    return {"round": round_, "answer_field": field, "agent_results": agent_results,
            "answer": answer, "tie_abstention": tied, "correct": correct,
            "scoring": cfg.outcome.scoring, "method": cfg.outcome.method}


def environment():
    versions = {}
    for name in ("pydantic", "PyYAML", "numpy", "torch", "transformers", "sentence-transformers"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            pass
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": versions}


def run(cfg, out_root, client_factory=Client):
    cases = load_cases(cfg.dataset)
    assignments = {c.id: allocate(c, cfg.agents, cfg.context) for c in cases}
    # Check the score contract before making any model calls.
    if cfg.outcome.scoring == "exact" and any(not c.reference.get("accepted_answers") for c in cases):
        raise ValueError("Exact scoring requires reference.accepted_answers in every case")
    run_id = f"{cfg.name}-{digest(cfg.model_dump())[:10]}-{uuid.uuid4().hex[:8]}"
    out = Path(out_root) / run_id
    out.mkdir(parents=True, exist_ok=False)
    source_hashes = {"dataset": file_hash(cfg.dataset.resolve_path())}
    if cfg.dataset.evidence_dictionary:
        source_hashes["evidence_dictionary"] = file_hash(cfg.dataset.resolve_path("evidence_dictionary"))
    manifest = {"schema_version": 1, "run_id": run_id, "status": "running",
                "config": cfg.model_dump(), "config_hash": digest(cfg.model_dump()),
                "code_hashes": code_snapshot(), "environment": environment(),
                "dataset_hashes": source_hashes,
                "source_location": str(cfg.dataset.resolve_path()), "case_ids": [c.id for c in cases],
                "case_hashes": {c.id: digest(c.model_dump()) for c in cases},
                "resolved_edges": edges(cfg), "assignments": assignments}
    atomic_json(out / "manifest.json", manifest)
    atomic_json(out / "cases.json", [{k:v for k,v in c.model_dump().items() if k != "reference"} for c in cases])
    atomic_json(out / "references.private.json", {c.id: c.reference for c in cases})
    atomic_json(out / "trace.json", {"cases": {}, "status": "running"})
    trace = {"cases": {}, "status": "running"}
    start = time.perf_counter()
    try:
        client = client_factory(cfg.generation, out / "calls" / "generation", cfg.dataset.allow_remote_processing)
        for case in cases:
            turns = []
            trace["cases"][case.id] = {"turns": turns, "round_outcomes": [], "status": "running"}
            agents = {a.id: a for a in cfg.agents}
            for rnd in range(1, cfg.rounds + 1):
                def one(agent_id):
                    messages, delivery = messages_for(cfg, case, agents[agent_id], rnd, turns, assignments[case.id])
                    response_type = DiagnosticAnswer if cfg.outcome.answer_field == "final_diagnosis" else AgentAnswer
                    value, info = client.request(messages, response_type,
                        f"replicate:{cfg.replicate}/case:{case.id}/agent:{agent_id}/round:{rnd}")
                    turn = {"id": f"{agent_id}|{rnd}", "agent_id": agent_id, "round": rnd,
                            "delivery": delivery, "messages": info.get("messages", messages),
                            "output_text": value.assessment + "\nFinal answer: " + value.answer,
                            "answer": value.answer, "call": info}
                    if isinstance(value, DiagnosticAnswer):
                        turn["final_diagnosis"] = value.final_diagnosis
                        turn["output_text"] += "\nFinal diagnosis: " + value.final_diagnosis
                    return turn
                if cfg.topology.schedule == "sequential":
                    for a in cfg.topology.order:
                        turns.append(one(a))
                        atomic_json(out / "trace.json", trace)
                else:
                    # Barrier: no append until the whole round has finished.
                    with ThreadPoolExecutor(max_workers=cfg.max_parallel) as pool:
                        round_turns = list(pool.map(one, cfg.topology.order))
                    turns.extend(round_turns)
                    atomic_json(out / "trace.json", trace)
                trace["cases"][case.id]["round_outcomes"].append(outcome(cfg, case, turns, rnd))
                atomic_json(out / "trace.json", trace)
            trace["cases"][case.id].update(status="complete", outcome=outcome(cfg, case, turns))
            atomic_json(out / "trace.json", trace)
        trace["status"] = manifest["status"] = "complete"
    except Exception as exc:
        trace["status"] = manifest["status"] = "failed"
        manifest["error_type"] = type(exc).__name__
        raise
    finally:
        manifest["generation_wall_seconds"] = time.perf_counter() - start
        atomic_json(out / "trace.json", trace)
        manifest["artifact_hashes"] = {name: file_hash(out / name) for name in ("cases.json", "references.private.json", "trace.json")}
        atomic_json(out / "manifest.json", manifest)
    return out
