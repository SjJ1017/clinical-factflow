import importlib.util
import json
from pathlib import Path
import pytest
from clinical_factflow.io import atomic_json, file_hash

spec = importlib.util.spec_from_file_location(
    "split_bundle", Path(__file__).parents[1] / "scripts/split_matching_bundle.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_complete_case_partition_is_disjoint_and_preserves_bytes(tmp_path):
    bundle = tmp_path / "input"
    bundle.mkdir()
    cases = []
    for i in range(4):
        f = bundle / f"{i}.json"
        atomic_json(f, {"case_id": str(i), "nodes": []})
        cases.append({"case_id": str(i), "file": f.name, "sha256": file_hash(f)})
    atomic_json(
        bundle / "manifest.json",
        {"complete": True, "cases": cases, "records": ["original"]},
    )
    profile = tmp_path / "profile.json"
    atomic_json(
        profile,
        {
            "input_complete": True,
            "input_manifest_sha256": file_hash(bundle / "manifest.json"),
            "cases": [
                {"case_id": str(i), "default_candidates": w}
                for i, w in enumerate([8, 7, 6, 5])
            ],
            "default": {"top_k": 12},
            "pairs_per_second_bidirectional": 7.25,
        },
    )
    plan = mod.split(bundle, profile, tmp_path / "split", ["gpu0", "gpu4"])
    assert [s["candidate_pairs"] for s in plan["shards"]] == [13, 13]
    assigned = []
    for shard in plan["shards"]:
        root = tmp_path / "split" / shard["name"]
        m = json.loads((root / "manifest.json").read_text())
        assert m["complete"] and m["records"] == ["original"]
        for c in m["cases"]:
            assigned.append(c["case_id"])
            assert (root / c["file"]).read_bytes() == (bundle / c["file"]).read_bytes()
    assert len(set(assigned)) == len(assigned) == 4
    with pytest.raises(FileExistsError):
        mod.split(bundle, profile, tmp_path / "split", ["gpu0", "gpu4"])
    atomic_json(
        profile, {**json.loads(profile.read_text()), "input_manifest_sha256": "wrong"}
    )
    with pytest.raises(ValueError, match="does not describe"):
        mod.split(bundle, profile, tmp_path / "other", ["gpu0", "gpu4"])
