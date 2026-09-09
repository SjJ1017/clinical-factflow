"""Explicit one-time public model download; write a revision-pinned matching YAML."""

import argparse
from pathlib import Path
import yaml
from huggingface_hub import snapshot_download
from clinical_factflow.server_matching import load_config


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("configs/matching/qwen14b.yaml"))
    p.add_argument("--out", type=Path, default=Path("outputs/matching-resolved.yaml"))
    args = p.parse_args()
    if args.out.exists():
        raise FileExistsError("Do not overwrite a pinned model configuration")
    cfg = load_config(args.config)
    for name in ["encoder", "scorer"]:
        c = cfg[name]
        if c["backend"] == "random_mock":
            continue
        path = Path(snapshot_download(c["model"], revision=c["revision"]))
        c["revision"] = path.name
        c["local_files_only"] = True
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print("Pinned local model settings:", args.out)


if __name__ == "__main__":
    main()
