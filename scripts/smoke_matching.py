"""Exercise the portable matching interface using explicitly synthetic logits."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from clinical_factflow.config import digest
from clinical_factflow.io import atomic_json, file_hash
from clinical_factflow.server_matching import connect, load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/matching/random-smoke.yaml")
    )
    args = parser.parse_args()
    config = args.config.resolve()
    if load_config(config)["scorer"]["backend"] != "random_mock":
        raise ValueError("This smoke script only permits synthetic model scores")
    args.out.mkdir(parents=True, exist_ok=False)
    bundle = args.out / "bundle"
    bundle.mkdir()
    entries = []
    templates = [
        "The patient has {x}.",
        "{x} is present.",
        "{x} was observed for two days.",
        "The patient does not have {x}.",
    ]
    for cid in ["synthetic-A", "synthetic-B"]:
        texts = [
            t.format(x=x)
            for x in ["fever", "cough", "fatigue", "anemia", "edema", "nausea"]
            for t in templates
        ]
        nodes = [
            dict(id=digest([cid, t]), text=t, qualifiers=[], logic_text=t, mentions=[])
            for t in texts
        ]
        f = bundle / (cid + ".json")
        atomic_json(f, dict(case_id=cid, nodes=nodes, test_data=True))
        entries.append(
            dict(
                case_id=cid,
                file=f.name,
                sha256=file_hash(f),
                nodes=len(nodes),
                pairs=len(nodes) * (len(nodes) - 1) // 2,
            )
        )
    atomic_json(
        bundle / "manifest.json",
        dict(version="atom-bundle-v1", complete=True, test_data=True, cases=entries),
    )
    out = args.out / "results"

    def cli(*items):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "clinical_factflow.server_matching",
                *map(str, items),
            ],
            check=True,
        )

    # Stop after one batch/case, then continue the same ledgers.
    cli("run", "--bundle", bundle, "--out", out, "--config", config, "--max-batches", 1)
    cli("run", "--bundle", bundle, "--out", out, "--config", config)

    def counts():
        result = []
        for f in sorted(out.glob("*.sqlite")):
            db = connect(f)
            result.append(db.execute("SELECT COUNT(*) FROM judgments").fetchone()[0])
            db.close()
        return result

    before = counts()
    cli("run", "--bundle", bundle, "--out", out, "--config", config)
    assert before == counts(), "Completed run unexpectedly made additional judgments"
    cli("export", "--results", out, "--out", args.out / "initial-labels")
    cli(
        "relabel",
        "--results",
        out,
        "--name",
        "expanded",
        "--blocker-threshold",
        0,
        "--top-k",
        100000,
    )
    cli("score", "--results", out, "--policy", "expanded", "--config", config)
    cli(
        "review",
        "--results",
        out,
        "--policy",
        "initial",
        "--out",
        args.out / "review",
        "--blocker-band",
        0.02,
        "--nli-band",
        0.5,
    )
    cli(
        "rejudge",
        "--results",
        out,
        "--policy",
        "initial",
        "--name",
        "boundary-review",
        "--pairs",
        args.out / "review",
        "--config",
        config,
    )
    cli(
        "export",
        "--results",
        out,
        "--policy",
        "boundary-review",
        "--out",
        args.out / "reviewed-labels",
    )
    total = sum(e["pairs"] for e in entries)
    rows = [
        json.loads(l)
        for f in (args.out / "reviewed-labels").glob("*.jsonl")
        for l in f.read_text().splitlines()
    ]
    assert len(rows) == total and all(
        r["status"] == "complete" and r["test_data"] for r in rows
    )
    result = dict(
        test_data=True,
        cases=2,
        nodes=48,
        pairs=total,
        initial_model_pairs=sum(before),
        completed_resume_new_judgments=0,
        all_pair_coverage=True,
        threshold_relabel=True,
        boundary_rejudge=True,
        real_gpu_validation=False,
    )
    atomic_json(args.out / "smoke-summary.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
