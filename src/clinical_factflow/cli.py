from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import RunConfig, differences, digest, load_config
from .datasets import allocate, load_cases
from .extraction import extract
from .matching import match
from .runner import edges, run


def main():
    parser = argparse.ArgumentParser(description="Controlled runs → extraction + atomization → local NLI")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "run", "extract", "match", "pipeline"):
        p = sub.add_parser(name)
        p.add_argument("config", type=Path)
        if name in ("run", "pipeline"):
            p.add_argument("--out", type=Path, default=Path("runs"))
        if name in ("extract", "match"):
            p.add_argument("--run-dir", type=Path, required=True)
        if name == "validate":
            p.add_argument("--with-data", action="store_true")
    p = sub.add_parser("compare")
    p.add_argument("a",type=Path)
    p.add_argument("b",type=Path)
    p.add_argument("--allow",nargs="*",default=["name", "topology.kind", "topology.hub"])
    p = sub.add_parser("schema")
    p.add_argument("--out",type=Path)
    args = parser.parse_args()
    if args.command == "schema":
        text = json.dumps(RunConfig.model_json_schema(),indent=2)
        if args.out:
            args.out.write_text(text+"\n")
        else:
            print(text)
        return
    if args.command == "compare":
        a,b = load_config(args.a),load_config(args.b)
        changed = differences(a.model_dump(),b.model_dump())
        unexpected = [p for p in changed if p not in args.allow]
        print(json.dumps({"changed":changed,"unexpected":unexpected},indent=2))
        if unexpected:
            raise SystemExit(1)
        return
    cfg = load_config(args.config)
    if args.command == "validate":
        result = {"config_hash": digest(cfg.model_dump()), "edges":edges(cfg),
                  "schedule":cfg.topology.schedule,"network_calls":0}
        if args.with_data:
            cases = load_cases(cfg.dataset)
            result["cases"] = [{"id":c.id,"evidence_count":len(c.evidence),
                "assignment":allocate(c,cfg.agents,cfg.context),
                "categories":sorted({e.category for e in c.evidence})} for c in cases]
        print(json.dumps(result,indent=2))
    elif args.command == "run":
        print(run(cfg,args.out))
    elif args.command == "extract":
        print(extract(cfg,args.run_dir))
    elif args.command == "match":
        print(match(cfg,args.run_dir))
    else:
        out = run(cfg,args.out)
        print(out,flush=True)
        extract(cfg,out)
        match(cfg,out)
