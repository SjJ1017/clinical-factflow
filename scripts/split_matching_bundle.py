"""Partition complete case inventories by measured candidate count, without changing atoms."""

import argparse
import json
import shutil
from pathlib import Path

from clinical_factflow.io import atomic_json, file_hash


def partition(cases, weights, names):
    groups = {name: [] for name in names}
    loads = {name: 0 for name in names}
    for case in sorted(cases, key=lambda c: (-weights[c["case_id"]], c["case_id"])):
        name = min(names, key=lambda n: (loads[n], len(groups[n]), n))
        groups[name].append(case)
        loads[name] += weights[case["case_id"]]
    return groups, loads


def split(bundle, profile, out, names):
    manifest = json.loads((bundle / "manifest.json").read_text())
    workload = json.loads(profile.read_text())
    parent_hash = file_hash(bundle / "manifest.json")
    if not manifest["complete"] or not workload["input_complete"]:
        raise ValueError("A complete extraction and workload profile are required")
    if workload["input_manifest_sha256"] != parent_hash:
        raise ValueError("Profile does not describe this bundle")
    if (
        not names
        or len(set(names)) != len(names)
        or any(Path(n).name != n or n in (".", "..") for n in names)
    ):
        raise ValueError("Shard names must be distinct directory basenames")
    weights = {c["case_id"]: c["default_candidates"] for c in workload["cases"]}
    if set(weights) != {c["case_id"] for c in manifest["cases"]}:
        raise ValueError("Profile case inventory mismatch")
    for case in manifest["cases"]:
        if file_hash(bundle / case["file"]) != case["sha256"]:
            raise ValueError("Case content changed")
    groups, loads = partition(manifest["cases"], weights, names)
    if any(not cases for cases in groups.values()):
        raise ValueError("Every shard must contain at least one case")
    out.mkdir(parents=True, exist_ok=False)
    plan = {
        "parent_manifest_sha256": parent_hash,
        "case_count": len(weights),
        "policy": workload["default"],
        "total_candidate_pairs": sum(loads.values()),
        "bidirectional_pairs_per_second": workload["pairs_per_second_bidirectional"],
        "shards": [],
    }
    for name, cases in groups.items():
        target = out / name
        target.mkdir()
        for case in cases:
            dest = target / case["file"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle / case["file"], dest)
            assert file_hash(dest) == case["sha256"]
        scope = {
            "name": name,
            "parent_manifest_sha256": parent_hash,
            "parent_case_count": len(weights),
            "selected_case_ids": [c["case_id"] for c in cases],
            "records_scope": "records and completed_records describe the complete parent extraction; cases is the selected shard",
        }
        atomic_json(
            target / "manifest.json", {**manifest, "cases": cases, "shard": scope}
        )
        plan["shards"].append(
            {
                **scope,
                "bundle": name,
                "candidate_pairs": loads[name],
                "estimated_gpu_hours": loads[name]
                / workload["pairs_per_second_bidirectional"]
                / 3600,
            }
        )
    assigned = [c for shard in plan["shards"] for c in shard["selected_case_ids"]]
    assert len(assigned) == len(set(assigned)) == len(weights)
    atomic_json(out / "plan.json", plan)
    return plan


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--profile", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--names", nargs="+", required=True)
    args = p.parse_args()
    print(json.dumps(split(args.bundle, args.profile, args.out, args.names), indent=2))


if __name__ == "__main__":
    main()
