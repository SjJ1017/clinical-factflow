"""Offline blocker workload profile; save every computed pair value for later policies."""

import argparse
import json
import time
from collections import Counter
from pathlib import Path
import numpy as np
from clinical_factflow.config import digest
from clinical_factflow.io import atomic_json, file_hash
from clinical_factflow.server_matching import geometry, get_encoder, load_config

PAIR_DTYPE = np.dtype(
    [
        (name, typ)
        for name, typ in [
            ("a", "i4"),
            ("b", "i4"),
            ("cosine", "f8"),
            ("lexical", "f8"),
            ("token_intersection", "i4"),
            ("a_token_count", "i4"),
            ("b_token_count", "i4"),
            ("combined", "f8"),
            ("rank_a", "i4"),
            ("rank_b", "i4"),
        ]
    ]
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--config", type=Path, default=Path("configs/matching/qwen14b.yaml"))
    p.add_argument("--pairs-per-second", type=float, default=7.25)
    args = p.parse_args()
    cfg = load_config(args.config)
    bundle = json.loads((args.bundle / "manifest.json").read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    encoder = None
    reports = []
    policies = [(t, 12) for t in [0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75, 0.80]] + [
        (0.62, k) for k in [6, 8, 20, 24, 32]
    ]
    started = time.perf_counter()
    for e in bundle["cases"]:
        f = args.bundle / e["file"]
        if file_hash(f) != e["sha256"]:
            raise ValueError("Case hash changed")
        case = json.loads(f.read_text())
        nodes = case["nodes"]
        stem = digest(case["case_id"])[:24]
        target = args.out / stem
        target.mkdir(exist_ok=True)
        signature = {
            "input_hash": e["sha256"],
            "encoder": cfg["encoder"],
            "geometry_source": file_hash(Path(geometry.__code__.co_filename)),
            "profile_source": file_hash(Path(__file__)),
        }
        cache = target / "pairs.npz"
        metadata = target / "geometry.json"
        if metadata.exists():
            old = json.loads(metadata.read_text())
            if old["signature"] != signature or file_hash(cache) != old["cache_sha256"]:
                raise ValueError("Frozen geometry changed; choose new output")
            pairs = np.load(cache)["pairs"]
        else:
            if encoder is None:
                encoder = get_encoder(cfg["encoder"])
            emb = encoder.encode([n["logic_text"] for n in nodes])
            # Same geometry function and tie-breaking as production, including lexicon scores.
            pairs = np.fromiter(
                (row[1:] for row in geometry(nodes, emb)),
                dtype=PAIR_DTYPE,
                count=e["pairs"],
            )
            tmp = target / "pairs.tmp.npz"
            np.savez_compressed(tmp, pairs=pairs, embeddings=emb)
            tmp.replace(cache)
            atomic_json(
                metadata,
                {
                    "signature": signature,
                    "cache_sha256": file_hash(cache),
                    "encoder_runtime": encoder.metadata,
                    "node_ids": [n["id"] for n in nodes],
                    "pair_id_recipe": "digest([node_ids[a],node_ids[b]])",
                },
            )
        ranks = np.minimum(pairs["rank_a"], pairs["rank_b"])
        scores = pairs["combined"]
        comparisons = []
        for threshold, k in policies:
            count = int(np.count_nonzero((scores >= threshold) & (ranks <= k)))
            comparisons.append(
                {
                    "threshold": threshold,
                    "top_k": k,
                    "candidate_pairs": count,
                    "gpu_seconds": count / args.pairs_per_second,
                }
            )
        default = (scores >= cfg["policy"]["blocker_threshold"]) & (
            ranks <= cfg["policy"]["top_k"]
        )
        owners = [
            {b["run_dir"] for m in n["mentions"] for b in m["bindings"]} for n in nodes
        ]
        traces = {t for ts in owners for t in ts}
        trace_counts = Counter({t: 0 for t in traces})
        cross_only = 0
        for row in pairs[default]:
            common = owners[row["a"]] & owners[row["b"]]
            if not common:
                cross_only += 1
            trace_counts.update(common)
        report = {
            "case_id": case["case_id"],
            "nodes": len(nodes),
            "all_pairs": len(pairs),
            "default_candidates": int(default.sum()),
            "default_cross_run_only": cross_only,
            "default_candidates_by_trace": dict(trace_counts),
            "policies": comparisons,
        }
        reports.append(report)
        atomic_json(target / "counts.json", report)
        print(
            json.dumps(
                {
                    k: v
                    for k, v in report.items()
                    if k not in ("policies", "default_candidates_by_trace")
                }
            ),
            flush=True,
        )
        atomic_json(
            args.out / "progress.json",
            {"completed_cases": len(reports), "cases": len(bundle["cases"])},
        )
    totals = []
    for i, (t, k) in enumerate(policies):
        count = sum(r["policies"][i]["candidate_pairs"] for r in reports)
        totals.append(
            {
                "threshold": t,
                "top_k": k,
                "candidate_pairs": count,
                "gpu_hours": count / args.pairs_per_second / 3600,
            }
        )
    trace_counts = Counter()
    for r in reports:
        trace_counts.update(r["default_candidates_by_trace"])
    result = {
        "complete": True,
        "input_complete": bundle["complete"],
        "input_records": bundle.get("completed_records"),
        "expected_records": bundle.get("expected_records"),
        "input_manifest_sha256": file_hash(args.bundle / "manifest.json"),
        "pairs_per_second_bidirectional": args.pairs_per_second,
        "default": cfg["policy"],
        "cases": reports,
        "total_nodes": sum(r["nodes"] for r in reports),
        "total_pairs": sum(r["all_pairs"] for r in reports),
        "total_default_candidates": sum(r["default_candidates"] for r in reports),
        "cross_run_only_default": sum(r["default_cross_run_only"] for r in reports),
        "per_trace_default_sum": sum(trace_counts.values()),
        "per_trace_default_mean": (
            float(np.mean(list(trace_counts.values()))) if trace_counts else None
        ),
        "policies": totals,
        "blocker_wall_seconds": time.perf_counter() - started,
        "note": "Real blocker. No NLI model calls. Shared case-level scoring pool, exact statement identities reused across runs. Partial inputs are not a full-study measurement.",
    }
    atomic_json(args.out / "summary.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}), flush=True)


if __name__ == "__main__":
    main()
