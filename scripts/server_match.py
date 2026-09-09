"""Run all-pair labeling and export a new immutable JSONL snapshot on the server."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--config", type=Path, default=Path("configs/matching/qwen14b.yaml"))
    args = p.parse_args()

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

    cli("run", "--bundle", args.bundle, "--out", args.out, "--config", args.config)
    index = json.loads((args.out / "index.json").read_text())
    if not index["complete"] or not index["input_complete"]:
        raise RuntimeError("Incomplete annotations; no complete export published")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    snapshot = args.out / "exports" / ("initial-" + stamp)
    cli("export", "--results", args.out, "--policy", "initial", "--out", snapshot)
    print("Complete annotation snapshot:", snapshot)


if __name__ == "__main__":
    main()
