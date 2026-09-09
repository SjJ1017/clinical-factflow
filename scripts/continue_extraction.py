"""Resume the frozen extraction engine, scheduling previous failures last.

Only scheduling changes: request keys, prompts, schema, cached stages and frozen
engine source stay identical. The additional scheduler has its own audit hash.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from clinical_factflow import resumable_extraction as engine
from clinical_factflow.io import atomic_json, file_hash

base_execute = engine.execute


def execute_deferred(tasks, cfg, target, deadline, stop):
    deferred = {p.stem for p in (target / "errors").glob("*.json")}
    ordered = sorted(tasks, key=lambda task: task["id"] in deferred)
    stamp = datetime.now(timezone.utc).isoformat().replace(":", "-")
    atomic_json(
        target / "sessions" / (stamp + ".schedule.json"),
        {
            "method": "previous_failures_last_v1",
            "scheduler_sha256": file_hash(Path(__file__)),
            "task_order": [t["id"] for t in ordered],
            "deferred_ids": sorted(deferred),
            "measurement_changes": False,
        },
    )
    return base_execute(ordered, cfg, target, deadline, stop)


if __name__ == "__main__":
    engine.execute = execute_deferred
    engine.main()
