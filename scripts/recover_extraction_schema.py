"""Versioned schema-only retry of failed stages; keep valid stages and atoms unchanged.

Run only after the normal queue stops. The queue's original manifest/source hashes
remain frozen; this opt-in retry has distinct request keys and a separate audit.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from clinical_factflow import resumable_extraction as engine
from clinical_factflow.config import digest
from clinical_factflow.io import atomic_json, file_hash

POLICY = "schema-validation-retry-v1"
FEEDBACK = """\nSCHEMA VALIDATION RETRY: The previous response used annotation values outside the supplied schema. Re-do this same task from the same target text and obey the schema exactly.
- annotation.kind is one of observation, inference, recommendation, general_knowledge, discourse. It describes the statement type, not the specialty. For example, a proposed treatment is a recommendation; a recorded treatment is an observation; a derived diagnosis is an inference. "treatment" and "diagnosis" are content domains, never kind values. Choose the kind from what the sentence actually asserts.
- clinical_domain is a list of the existing domain values. "other" is exclusive and must not appear alongside a specific domain. Use ["other"] only when none of the specific domains apply.
- Do not change the target text, add facts, import outside context, or omit facts to avoid a schema error. Keep all required qualifiers and original quotations.\n"""
BaseCheckpointClient = engine.CheckpointClient
base_execute = engine.execute


class SchemaRetryClient(BaseCheckpointClient):
    def request(self, messages, response_model, sample_id, validate=None):
        original_key = digest(
            [
                sample_id,
                messages,
                response_model.model_json_schema(),
                self.settings.model_dump(),
            ]
        )
        if (self.directory / "checkpoints" / (original_key + ".json")).exists():
            return super().request(messages, response_model, sample_id, validate)
        logs = []
        for p in (self.directory / "calls").glob("*.json"):
            c = json.loads(p.read_text())
            if c["sample_id"] == sample_id:
                logs.append(c)
        # Recover a valid raw reply through the unchanged original mechanism.
        if any(c.get("status") == "ok" for c in logs):
            return super().request(messages, response_model, sample_id, validate)
        if not any(c.get("error_type") == "ValidationError" for c in logs):
            return super().request(messages, response_model, sample_id, validate)
        corrected = [dict(m) for m in messages]
        corrected[0]["content"] += FEEDBACK
        retry_id = sample_id + "/" + POLICY
        key = digest(
            [
                retry_id,
                corrected,
                response_model.model_json_schema(),
                self.settings.model_dump(),
            ]
        )
        audit = {
            "policy": POLICY,
            "original_sample_id": sample_id,
            "original_request_key": original_key,
            "retry_sample_id": retry_id,
            "retry_request_key": key,
            "script_sha256": file_hash(Path(__file__)),
            "failed_call_ids": [
                c["call_id"] for c in logs if c.get("error_type") == "ValidationError"
            ],
            "feedback": FEEDBACK,
            "schema_unchanged": True,
            "atoms_manually_modified": False,
        }
        atomic_json(self.directory / "schema-retries" / (original_key + ".json"), audit)
        value, info = super().request(corrected, response_model, retry_id, validate)
        return value, {
            **info,
            "schema_retry": {
                k: audit[k]
                for k in (
                    "policy",
                    "original_sample_id",
                    "original_request_key",
                    "retry_request_key",
                    "script_sha256",
                )
            },
        }


def execute_recovery(tasks, cfg, target, deadline, stop):
    pending = [
        t["id"]
        for t in tasks
        if not (target / "results" / (t["id"] + ".json")).exists()
    ]
    stamp = datetime.now(timezone.utc).isoformat().replace(":", "-")
    atomic_json(
        target / "sessions" / (stamp + ".schema-retry.json"),
        {
            "policy": POLICY,
            "script_sha256": file_hash(Path(__file__)),
            "pending_task_ids": pending,
            "feedback": FEEDBACK,
            "original_manifest_unchanged": True,
        },
    )
    return base_execute(tasks, cfg, target, deadline, stop)


if __name__ == "__main__":
    engine.CheckpointClient = SchemaRetryClient
    engine.execute = execute_recovery
    engine.main()
