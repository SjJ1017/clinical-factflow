import importlib.util
import json
import threading
import time
from pathlib import Path
from clinical_factflow.config import load_config, digest
from clinical_factflow.models import Atom, Extracted
from clinical_factflow.resumable_extraction import CheckpointClient

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "schema_retry", ROOT / "scripts/recover_extraction_schema.py"
)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def test_schema_retry_changes_only_failed_stage_key_and_keeps_target(tmp_path):
    settings = load_config(ROOT / "configs/demo-full.yaml").extraction.model
    messages = [
        dict(role="system", content="Extract."),
        dict(role="user", content="Only this output."),
    ]
    atom = Atom(
        text="Fever.",
        quote="Fever.",
        qualifiers=[],
        annotation=dict(
            kind="observation",
            attribution="direct",
            certainty="asserted",
            polarity="affirmed",
            clinical_domain=["history"],
        ),
    )
    calls = []

    class Fake:
        def __init__(self, *a):
            pass

        def request(self, msg, response_model, sample_id, validate=None):
            calls.append((msg, sample_id))
            return Extracted(facts=[atom]), {}

    task = tmp_path / "task"
    (task / "calls").mkdir(parents=True)
    (task / "calls" / "failed.json").write_text(
        json.dumps(
            dict(
                call_id="failed",
                sample_id="t/extract",
                status="failed",
                error_type="ValidationError",
            )
        )
    )
    client = recovery.SchemaRetryClient(
        settings, task, True, threading.Event(), time.time() + 60, Fake
    )
    a, info = client.request(messages, Extracted, "t/extract")
    b, _ = client.request(messages, Extracted, "t/extract")
    assert a == b and len(calls) == 1
    assert calls[0][0][1] == messages[1]
    assert calls[0][1] == "t/extract/schema-validation-retry-v1"
    assert info["schema_retry"]["original_sample_id"] == "t/extract"
    original = digest(
        ["t/extract", messages, Extracted.model_json_schema(), settings.model_dump()]
    )
    assert not (task / "checkpoints" / (original + ".json")).exists()
    # A completed original request still uses its original checkpoint, without feedback.
    valid = tmp_path / "valid"
    base = CheckpointClient(
        settings, valid, True, threading.Event(), time.time() + 60, Fake
    )
    base.request(messages, Extracted, "t/extract")
    count = len(calls)
    resumed = recovery.SchemaRetryClient(
        settings, valid, True, threading.Event(), time.time() + 60, Fake
    )
    resumed.request(messages, Extracted, "t/extract")
    assert len(calls) == count
