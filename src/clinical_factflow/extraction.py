from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .client import Client
from .config import digest
from .io import atomic_json, file_hash, verify_run
from .models import Extracted, SplitResult


def require_facts(result):
    if not result.facts:
        raise ValueError("Empty extraction from nonempty input")


def validate_splits(result, parents):
    got = [x.parent_id for x in result.facts]
    if len(got) != len(set(got)) or set(got) != set(parents):
        raise ValueError("Atomization must cover each parent exactly once")


def spans(text, quote):
    return [[m.start(), m.end()] for m in re.finditer(re.escape(quote), text)]


def extract_record(client, cfg, record):
    # Deliberately ignore legacy reference_context. Input profiles must reuse
    # extracted source/self/peer records instead of re-extracting input here.
    payload = json.dumps({"text": record["text"]}, ensure_ascii=False)
    result, info = client.request([
        {"role": "system", "content": cfg.system_prompt}, {"role": "user", "content": payload}],
        Extracted, record["id"] + "/extract", validate=require_facts)
    parents = {f"p{i}": f for i,f in enumerate(result.facts)}
    atoms = []
    batch_size = cfg.atomize_batch_size
    parent_ids = list(parents)
    split_calls = []
    for start in range(0, len(parent_ids), batch_size):
        keys = parent_ids[start:start+batch_size]
        batch = {k: parents[k].model_dump() for k in keys}
        user = json.dumps({"parents": batch, "original_text": record["text"]}, ensure_ascii=False)
        split, call = client.request([
            {"role": "system", "content": cfg.atomize_prompt}, {"role": "user", "content": user}],
            SplitResult, record["id"] + f"/atomize/{start}", validate=lambda r: validate_splits(r, keys))
        split_calls.append(call)
        # Model ordering cannot silently change mention identity.
        by_parent = {x.parent_id: x.parts for x in split.facts}
        for key in keys:
            for atom in by_parent[key]:
                atoms.append((key, atom))
    mentions, seen = [], {}
    for key, atom in atoms:
        # Kind/attribution are occurrence properties: never drop an inference
        # just because an observation in the same turn uses identical words.
        norm = digest([" ".join(atom.text.split()), atom.qualifiers, atom.annotation.model_dump()])
        locations = spans(record["text"], atom.quote)
        occurrence = {"parent_id": key, "quote": atom.quote, "spans": locations,
                      "span_status": "located" if locations else "unlocated"}
        if norm in seen:
            seen[norm]["occurrences"].append(occurrence)
            continue
        mention = {"id": "m_" + digest([record["id"], norm])[:24],
                   **atom.model_dump(), "provenance": record["provenance"],
                   "record_id": record["id"], "occurrences": [occurrence]}
        seen[norm] = mention
        mentions.append(mention)
    return {"record_id": record["id"], "record_hash": digest(record),
            "parents": {k:v.model_dump() for k,v in parents.items()}, "mentions": mentions,
            "extraction_call": info, "atomize_calls": split_calls}


def records_for(cfg, cases, trace):
    for case in cases:
        cid = case["id"]
        for e in case["evidence"]:
            yield {"id": f"{cid}/source/{e['id']}", "text": e["text"],
                   "provenance": {"case_id": cid, "channel": "source", "source_id": e["id"], "category": e["category"]}}
        for agent in cfg.agents:
            if agent.initial_context:
                yield {"id": f"{cid}/initial/{agent.id}", "text": agent.initial_context,
                       "provenance": {"case_id": cid, "channel": "initial", "agent_id": agent.id}}
        for turn in trace["cases"][cid]["turns"]:
            # Only this output is sent for extraction; provenance stays local.
            yield {"id": f"{cid}/output/{turn['id']}", "text": turn["output_text"],
                   "provenance": {"case_id": cid, "channel": "output", "agent_id": turn["agent_id"],
                                  "round": turn["round"], "turn_id": turn["id"]}}


def extract(cfg, run_dir, client_factory=Client):
    out = Path(run_dir)
    manifest = verify_run(cfg, out)
    if manifest["status"] != "complete":
        raise ValueError("Cannot extract a failed/incomplete generation run")
    for name in ("cases.json", "trace.json"):
        if file_hash(out / name) != manifest["artifact_hashes"][name]:
            raise ValueError(f"Frozen artifact changed: {name}")
    target = out / "extraction"
    client = client_factory(cfg.extraction.model, out / "calls" / "extraction", cfg.dataset.allow_remote_processing)
    target.mkdir(exist_ok=False)  # Never mix a retry corpus into a previous extraction.
    cases = json.loads((out / "cases.json").read_text())
    trace = json.loads((out / "trace.json").read_text())
    index = {"status": "running", "records": [], "config_hash": manifest["config_hash"]}
    atomic_json(target / "index.json", index)
    try:
        records = list(records_for(cfg, cases, trace))
        def one(record):
            result = extract_record(client, cfg.extraction, record)
            name = digest(record["id"])[:24] + ".json"
            atomic_json(target / name, result)
            return {"id": record["id"], "file": name, "hash": file_hash(target / name)}
        with ThreadPoolExecutor(max_workers=cfg.extraction.max_parallel) as pool:
            for record in pool.map(one, records):
                index["records"].append(record)
                atomic_json(target / "index.json", index)
        index["status"] = "complete"
    except Exception as exc:
        index.update(status="failed", error_type=type(exc).__name__)
        raise
    finally:
        atomic_json(target / "index.json", index)
    return target
