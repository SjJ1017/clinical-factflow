from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml
from pydantic import Field, PrivateAttr, model_validator
from .models import Strict


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


class Model(Strict):
    model: str
    base_url: str
    api_key_env: str | None = None
    temperature: float = Field(ge=0, le=2)
    max_tokens: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)
    attempts: int = Field(ge=1, le=5)
    seed: int | None = None
    extra_body: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def endpoint(self):
        p = urlparse(self.base_url)
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or p.query:
            raise ValueError("base_url must be an HTTP(S) URL without embedded credentials")
        forbidden = {"model", "messages", "temperature", "max_tokens", "seed", "stream"}
        if forbidden & self.extra_body.keys():
            raise ValueError("extra_body cannot override controlled model/request fields")
        return self

    def remote(self):
        return urlparse(self.base_url).hostname not in {"localhost", "127.0.0.1", "::1"}


class Dataset(Strict):
    _base_dir: Path = PrivateAttr(default_factory=Path.cwd)
    adapter: Literal["canonical", "clinicalbench", "ddxplus", "medcasereasoning"]
    path: str
    evidence_dictionary: str | None = None
    task: str
    case_ids: list[str] | None = None
    limit: int | None = Field(default=None, gt=0)
    selection_seed: int
    allow_remote_processing: bool
    # Input transformations are explicit; these do not grant a data license.
    clinical_summary_stop: str | None = "Auxiliary Examination"
    clinical_include_impressions: bool = False

    def resolve_path(self, field="path") -> Path:
        value = getattr(self, field)
        if value is None:
            raise ValueError(f"No dataset path configured for {field}")
        return (self._base_dir / value).resolve()


class Agent(Strict):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    role: str
    prompt: str
    initial_context: str = ""


class Topology(Strict):
    kind: Literal["full", "star", "chain", "none", "custom"]
    schedule: Literal["synchronous", "sequential"]
    hub: str | None = None
    order: list[str]
    edges: list[tuple[str, str]] = Field(default_factory=list)


class Context(Strict):
    distribution: Literal["shared", "round_robin", "by_category", "explicit"]
    assignments: dict[str, list[str]] = Field(default_factory=dict)
    evidence_visibility: Literal["every_round", "first_round"]
    self_memory: Literal["none", "last", "all"]
    peer_memory: Literal["last", "all"]


class Outcome(Strict):
    method: Literal["majority", "agent"]
    agent: str | None = None
    scoring: Literal["exact", "ungraded"]


class Extraction(Strict):
    model: Model
    system_prompt: str
    atomize_prompt: str
    atomize_batch_size: int = Field(gt=0)
    # All mentions receive the second pass; no lossy conjunction prefilter.
    atomize: Literal["all"]


class Matching(Strict):
    model: str = "Qwen/Qwen3-14B"
    revision: str = "main"
    dtype: Literal["bfloat16", "float16", "float32"] = "bfloat16"
    device: str = "cuda"
    batch_size: int = Field(default=16, gt=0)
    load_4bit: bool = False
    local_files_only: bool = True
    entailment_threshold: float = 5.28
    threshold_provenance: str
    blocker_model: str = "BAAI/bge-base-en-v1.5"
    blocker_revision: str = "main"
    blocker_threshold: float = Field(default=0.62, ge=0, le=1)
    blocker_top_k: int = Field(default=12, gt=0)
    blocker_metric: Literal["max_cosine_containment"] = "max_cosine_containment"
    system_prompt: str
    user_template: str
    cluster_policy: Literal["complete_link"] = "complete_link"


class RunConfig(Strict):
    schema_version: Literal[1]
    name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    replicate: int = Field(ge=0)
    dataset: Dataset
    agents: list[Agent] = Field(min_length=1)
    topology: Topology
    context: Context
    rounds: int = Field(gt=0)
    max_parallel: int = Field(gt=0)
    task_prompt: str
    generation: Model
    outcome: Outcome
    extraction: Extraction
    matching: Matching

    @model_validator(mode="after")
    def consistency(self):
        ids = [a.id for a in self.agents]
        if len(ids) != len(set(ids)) or sorted(self.topology.order) != sorted(ids):
            raise ValueError("Agent IDs must be unique; topology.order must list each exactly once")
        t = self.topology
        if t.kind == "star" and t.hub not in ids:
            raise ValueError("star requires a valid hub")
        if t.kind != "star" and t.hub is not None:
            raise ValueError("hub only applies to star")
        if t.kind != "custom" and t.edges:
            raise ValueError("edges only applies to custom")
        if len(t.edges) != len(set(t.edges)) or any(a not in ids or b not in ids or a == b for a, b in t.edges):
            raise ValueError("Invalid or duplicate custom edges")
        if t.schedule == "sequential" and t.kind not in {"chain", "custom"}:
            raise ValueError("Sequential execution requires chain or a custom DAG")
        if t.schedule == "sequential" and any(t.order.index(a) >= t.order.index(b) for a,b in t.edges):
            raise ValueError("Sequential edges must follow topology.order")
        c = self.context
        if c.distribution in {"by_category", "explicit"} and set(c.assignments) != set(ids):
            raise ValueError("Each agent needs an explicit assignment")
        if c.distribution in {"shared", "round_robin"} and c.assignments:
            raise ValueError("assignments is unused for shared/round_robin; remove it")
        if self.outcome.method == "agent" and self.outcome.agent not in ids:
            raise ValueError("outcome.agent must identify an agent")
        if self.outcome.method == "majority" and self.outcome.agent is not None:
            raise ValueError("outcome.agent is unused for majority")
        return self


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_config(path: str | Path) -> RunConfig:
    path = Path(path).resolve()
    raw = yaml.load(path.read_text(), Loader=UniqueLoader)
    cfg = RunConfig.model_validate(raw)
    # Resolve I/O locally without putting host-specific absolute paths into the
    # experiment fingerprint. Frozen data checksums identify the actual inputs.
    cfg.dataset._base_dir = path.parent
    return cfg


def differences(a, b, prefix="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        return [p for k in sorted(a.keys() | b.keys()) for p in
                (differences(a[k], b[k], f"{prefix}.{k}".strip(".")) if k in a and k in b
                 else [f"{prefix}.{k}".strip(".")])]
    return [] if a == b else [prefix]
