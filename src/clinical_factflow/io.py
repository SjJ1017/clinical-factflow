from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from .config import digest


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(1024 * 1024):
            h.update(b)
    return h.hexdigest()


def code_snapshot():
    root = Path(__file__).parent
    return {p.name: file_hash(p) for p in sorted(root.glob("*.py"))}


def verify_run(cfg, run_dir):
    manifest = json.loads((Path(run_dir) / "manifest.json").read_text())
    if manifest["config_hash"] != digest(cfg.model_dump()):
        raise ValueError("YAML differs from this run's frozen configuration")
    if manifest["code_hashes"] != code_snapshot():
        raise ValueError("Pipeline code differs from this run; use a new run rather than mixing versions")
    return manifest
