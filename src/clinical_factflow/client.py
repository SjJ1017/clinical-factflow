"""Small OpenAI-compatible HTTP client with per-attempt audit, no generation cache."""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse
import uuid

from .config import digest
from .io import atomic_json


def json_object(text):
    text = text.strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    elif text.startswith("```\n") and text.endswith("```"):
        text = text[4:-3].strip()
    return json.loads(text)


class Client:
    def __init__(self, settings, audit_dir, allow_remote):
        self.settings, self.audit_dir = settings, audit_dir
        self.session_namespace = uuid.uuid4().hex
        if settings.remote() and not allow_remote:
            raise ValueError("Dataset disallows remote processing; configure a local endpoint or obtain permission first")

    def request(self, messages, response_model, sample_id, validate=None):
        s = self.settings
        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        messages = [dict(m) for m in messages]
        messages[0]["content"] += "\nReturn one JSON object matching this schema. No markdown.\n" + schema
        payload = {"model": s.model, "messages": messages, "temperature": s.temperature,
                   "max_tokens": s.max_tokens, "stream": False, **s.extra_body}
        if s.seed is not None:
            # Deterministic, distinct agent/case/turn streams; paired across topology conditions.
            payload["seed"] = int(digest([s.seed, sample_id])[:8], 16)
        headers = {"Content-Type": "application/json", "User-Agent": "clinical-factflow/0.1"}
        if s.api_key_env:
            key = os.environ.get(s.api_key_env)
            if not key:
                raise ValueError(f"Missing environment variable {s.api_key_env}")
            headers["Authorization"] = "Bearer " + key
        # Provider routing session: stable per agent conversation and retries.
        # This is our own client/session identity, not an impersonated coding client.
        conversation = sample_id.split("/round:")[0].split("/atomize/")[0]
        if conversation.endswith("/extract"):
            conversation = conversation[:-8]
        session_id = "clinical-factflow-" + digest([self.session_namespace, conversation])[:32]
        if urllib.parse.urlparse(s.base_url).hostname == "opencode.ai":
            headers["x-opencode-session"] = session_id
        last = None
        for attempt in range(1, s.attempts + 1):
            call_id = uuid.uuid4().hex
            log = {"call_id": call_id, "sample_id": sample_id, "attempt": attempt,
                   "endpoint": s.base_url, "session_id": session_id, "request": payload}
            start = time.perf_counter()
            try:
                request = urllib.request.Request(s.base_url.rstrip("/") + "/chat/completions",
                    data=json.dumps(payload).encode(), headers=headers, method="POST")
                with urllib.request.urlopen(request, timeout=s.timeout_seconds) as f:
                    raw = json.load(f)
                log["response"] = raw
                choice = raw["choices"][0]
                if choice.get("finish_reason") in {"length", "content_filter"}:
                    raise ValueError(f"Incomplete response: {choice['finish_reason']}")
                value = response_model.model_validate(json_object(choice["message"]["content"]))
                if validate:
                    validate(value)
                log["status"] = "ok"
                return value, {"call_id": call_id, "usage": raw.get("usage"),
                               "response_model": raw.get("model"), "system_fingerprint": raw.get("system_fingerprint"),
                               "raw_text": choice["message"]["content"], "messages": messages,
                               "latency_seconds": time.perf_counter() - start}
            except Exception as exc:
                last = exc
                # Avoid provider exception bodies that could echo credentials or sensitive requests.
                log.update(status="failed", error_type=type(exc).__name__)
                if isinstance(exc, urllib.error.HTTPError):
                    log["http_status"] = exc.code
            finally:
                log["wall_seconds"] = time.perf_counter() - start
                atomic_json(self.audit_dir / f"{call_id}.json", log)
        raise RuntimeError(f"{sample_id}: all {s.attempts} attempts failed ({type(last).__name__}); see private call audit") from last
