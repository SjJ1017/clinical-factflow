import copy
import json
import math
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from clinical_factflow.config import digest
from clinical_factflow.io import atomic_json, file_hash
from clinical_factflow.pair_backends import (
    RandomEncoder,
    RandomLogitScorer,
    QwenLogitScorer,
)
from clinical_factflow.resumable_extraction import sealed_write
from clinical_factflow.server_matching import (
    init_case,
    create_policy,
    score_policy,
    summary,
    export_rows,
    export_bundle,
    geometry,
    validate_scores,
    scorer_hash,
    load_config,
    connect,
    meta,
)

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config(ROOT / "configs/matching/random-smoke.yaml")
TEXTS = [
    "The patient has fever.",
    "The patient has a fever.",
    "The patient has cough.",
    "Chest imaging shows a lung mass.",
    "Chest imaging shows a mass.",
    "Sodium is 130 mmol/L.",
    "The biopsy shows inflammation.",
    "Culture detects bacteria.",
]


def case(cid="synthetic"):
    nodes = [
        dict(id=digest([cid, t]), text=t, qualifiers=[], logic_text=t, mentions=[])
        for t in TEXTS
    ]
    return dict(case_id=cid, nodes=nodes, test_data=True)


def ledger(tmp_path, threshold=0.4, topk=4):
    c = case()
    db = init_case(tmp_path / "x.sqlite", c, RandomEncoder(1729, 24), CFG, digest(c))
    create_policy(db, "initial", threshold, topk, 5.28, scorer_hash(CFG))
    return db


class Counting(RandomLogitScorer):
    def __init__(self):
        super().__init__(31415)
        self.calls = []

    def score(self, pairs, round_id="initial"):
        self.calls.extend((p["pair_id"], round_id) for p in pairs)
        return super().score(pairs, round_id)


def test_all_pairs_are_explicit_and_geometry_agrees(tmp_path):
    db = ledger(tmp_path)
    s = summary(db, "initial")
    assert s["pair_universe"] == 28
    rows = list(db.execute("SELECT * FROM pairs"))
    assert len(rows) == 28 and all(
        r["combined"] == max(r["cosine"], r["lexical"]) for r in rows
    )
    for r in rows:
        assert r["lexical"] == r["token_intersection"] / min(
            r["a_token_count"], r["b_token_count"]
        )
        a = db.execute(
            "SELECT * FROM annotations WHERE pair_id=?", (r["pair_id"],)
        ).fetchone()
        escalated = r["combined"] >= 0.4 and min(r["rank_a"], r["rank_b"]) <= 4
        assert (a["relation"] is None) == escalated
        if not escalated:
            assert (a["relation"], a["status"], a["decision_stage"]) == (
                "UNRELATED",
                "complete",
                "blocker",
            )
    scorer = Counting()
    score_policy(db, "initial", scorer, 7)
    assert summary(db, "initial")["complete"]
    # Same label regardless of deciding stage; only provenance differs.
    assert (
        db.execute(
            "SELECT COUNT(*) FROM annotations WHERE relation='UNRELATED' AND decision_stage='nli'"
        ).fetchone()[0]
        > 0
    )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM annotations WHERE relation='UNRELATED' AND decision_stage='blocker'"
        ).fetchone()[0]
        > 0
    )


def test_resume_does_not_rescore_completed_pairs(tmp_path):
    db = ledger(tmp_path)
    scorer = Counting()
    score_policy(db, "initial", scorer, 2, max_batches=1)
    assert len(scorer.calls) == 2 and not summary(db, "initial")["complete"]
    db.close()
    db = init_case(
        tmp_path / "x.sqlite", case(), RandomEncoder(1729, 24), CFG, digest(case())
    )
    score_policy(db, "initial", scorer, 2)
    count = len(scorer.calls)
    score_policy(db, "initial", scorer, 2)
    assert count == len(scorer.calls) == len(set(scorer.calls))
    assert summary(db, "initial")["complete"]


@pytest.mark.parametrize(
    "defect", ["missing", "duplicate", "nan", "margin", "exception"]
)
def test_failure_cannot_become_unrelated(tmp_path, defect):
    db = ledger(tmp_path)
    before = list(
        db.execute("SELECT pair_id,relation FROM annotations WHERE relation IS NULL")
    )

    class Bad(Counting):
        def score(self, pairs, round_id="initial"):
            if defect == "exception":
                raise RuntimeError("Simulated local model failure")
            out = super().score(pairs, round_id)
            if defect == "missing":
                out.pop()
            if defect == "duplicate":
                out.append(out[0])
            if defect == "nan":
                out[0]["ab"]["margin"] = float("nan")
            if defect == "margin":
                out[0]["ab"]["margin"] += 1
            return out

    with pytest.raises((ValueError, RuntimeError)):
        score_policy(db, "initial", Bad(), 7)
    assert (
        list(
            db.execute(
                "SELECT pair_id,relation FROM annotations WHERE relation IS NULL"
            )
        )
        == before
    )
    assert db.execute("SELECT COUNT(*) FROM judgments").fetchone()[0] == 0
    assert db.execute("SELECT status FROM attempts").fetchone()[0] == "failed"
    score_policy(db, "initial", Counting(), 7)
    assert summary(db, "initial")["complete"]


def test_threshold_relabel_preserves_values_and_promotes_pending(tmp_path):
    db = ledger(tmp_path)
    scorer = Counting()
    score_policy(db, "initial", scorer, 7)
    old = [tuple(r) for r in db.execute("SELECT * FROM judgments")]
    old_annotations = [
        tuple(r) for r in db.execute("SELECT * FROM annotations WHERE policy='initial'")
    ]
    create_policy(db, "margin99", 0.4, 4, 99, scorer_hash(CFG), "initial")
    assert summary(db, "margin99")["complete"]
    assert (
        db.execute(
            "SELECT COUNT(*) FROM annotations WHERE policy='margin99' AND relation!='UNRELATED'"
        ).fetchone()[0]
        == 0
    )
    create_policy(db, "expanded", 0, 99, 5.28, scorer_hash(CFG), "initial")
    assert not summary(db, "expanded")["complete"]
    assert [tuple(r) for r in db.execute("SELECT * FROM judgments")] == old
    score_policy(db, "expanded", scorer, 7)
    assert len(scorer.calls) == 28
    assert [
        tuple(r) for r in db.execute("SELECT * FROM annotations WHERE policy='initial'")
    ] == old_annotations


def test_review_includes_blocker_negatives_and_keeps_old_judgment(tmp_path):
    db = ledger(tmp_path)
    scorer = Counting()
    score_policy(db, "initial", scorer, 7)
    out = tmp_path / "review.jsonl"
    assert export_rows(db, "initial", out, blocker_band=1, nli_band=100) == 28
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert any(
        r["decision_stage"] == "blocker" and r["relation"] == "UNRELATED" for r in rows
    )
    candidate = next(r for r in rows if r["judgment_id"])
    rejected = next(r for r in rows if not r["judgment_id"])
    ids = {candidate["pair_id"], rejected["pair_id"]}
    create_policy(db, "second", 0.4, 4, 5.28, scorer_hash(CFG), "initial", ids)
    before = len(scorer.calls)
    score_policy(db, "second", scorer, 7)
    assert len(scorer.calls) - before == 2
    judgments = list(
        db.execute("SELECT * FROM judgments WHERE pair_id=?", (candidate["pair_id"],))
    )
    assert len(judgments) == 2 and judgments[0]["payload"] != judgments[1]["payload"]
    assert (
        db.execute(
            "SELECT judgment_id FROM annotations WHERE policy='initial' AND pair_id=?",
            (candidate["pair_id"],),
        ).fetchone()[0]
        == candidate["judgment_id"]
    )
    for r in rows:
        if r["judgment"]:
            assert r["judgment"]["ab"]["margin"] == pytest.approx(r["ab_margin"])
            assert r["test_data"] is True


def test_random_logits_are_batch_and_order_independent():
    pairs = [dict(pair_id=str(i), a_text="a", b_text="b") for i in range(17)]
    scorer = RandomLogitScorer(3)
    all_scores = scorer.score(pairs)
    assert all_scores == sum(
        (scorer.score(pairs[i : i + 4]) for i in range(0, 17, 4)), []
    )
    assert all_scores == list(reversed(scorer.score(list(reversed(pairs)))))
    validate_scores(all_scores, pairs)
    assert all_scores != scorer.score(pairs, "review:second")


def test_bundle_preserves_qualifiers_case_separation_and_bindings(tmp_path):
    source = tmp_path / "source"
    tasks = []
    for i, (cid, qualifiers) in enumerate(
        [("one", []), ("one", ["for two days"]), ("two", []), ("one", [])]
    ):
        task = dict(
            id=str(i),
            record=dict(id=str(i), text="Fever.", provenance={"case_id": cid}),
            bindings=[{"run": str(i)}, {"run": str(i) + "-other"}],
        )
        tasks.append(task)
        mention = dict(
            id="m" + str(i),
            text="Fever.",
            qualifiers=qualifiers,
            quote="Fever.",
            annotation={},
        )
        sealed_write(
            source / "results" / f"{i}.json",
            dict(
                task_hash=digest(task),
                result=dict(record_hash=digest(task["record"]), mentions=[mention]),
            ),
        )
    sealed_write(source / "manifest.json", {"tasks": tasks})
    doc = export_bundle(source, tmp_path / "bundle")
    assert doc["complete"] and len(doc["cases"]) == 2
    one = next(c for c in doc["cases"] if c["case_id"] == "one")
    assert one["nodes"] == 2 and one["pairs"] == 1
    nodes = json.loads((tmp_path / "bundle" / one["file"]).read_text())["nodes"]
    assert sum(len(n["mentions"]) for n in nodes) == 3
    assert sum(len(m["bindings"]) for n in nodes for m in n["mentions"]) == 6
    assert any("Qualifiers: for two days" in n["logic_text"] for n in nodes)
    (source / "results/0.json").unlink()
    with pytest.raises(ValueError, match="incomplete"):
        export_bundle(source, tmp_path / "incomplete")
    assert not export_bundle(source, tmp_path / "partial", True)["complete"]


def test_changed_scorer_settings_and_input_are_rejected(tmp_path):
    db = ledger(tmp_path)
    db.close()
    new = copy.deepcopy(CFG)
    new["scorer"]["seed"] += 1
    with pytest.raises(ValueError, match="changed"):
        init_case(tmp_path / "x.sqlite", case(), RandomEncoder(), new, digest(case()))
    with pytest.raises(ValueError, match="changed"):
        init_case(tmp_path / "x.sqlite", case(), RandomEncoder(), CFG, "changed")


def test_real_logit_adapter_with_fake_local_forward():
    torch = pytest.importorskip("torch")

    class Enc(dict):
        def to(self, device):
            return self

    class Tokenizer:
        def apply_chat_template(self, messages, **kw):
            assert kw["enable_thinking"] is False
            return messages[1]["content"]

        def __call__(self, strings, **kw):
            assert kw["truncation"] is False
            return Enc(input_ids=torch.ones((len(strings), 3), dtype=torch.int64))

    class Net:
        device = "cpu"
        config = SimpleNamespace(max_position_embeddings=100)

        def forward(self, input_ids, logits_to_keep=0):
            assert logits_to_keep == 1
            return SimpleNamespace(
                logits=torch.tensor([[[0.0, 8.0, 1.0, 2.0]]] * len(input_ids))
            )

        __call__ = forward

    scorer = QwenLogitScorer.__new__(QwenLogitScorer)
    scorer.cfg = SimpleNamespace(
        system_prompt="Judge.", user_template="A: {a}\nB: {b}", batch_size=2
    )
    scorer.tok = Tokenizer()
    scorer.net = Net()
    scorer.ids = {"YES": [1], "NO": [2]}
    scorer.metadata = {"effective_batch_sizes": []}
    pairs = [dict(pair_id=str(i), a_text="x", b_text="y") for i in range(3)]
    scores = scorer.score(pairs)
    validate_scores(scores, pairs)
    assert all(p["ab"]["margin"] == pytest.approx(7) for p in scores)
    assert scorer.metadata["effective_batch_sizes"] == [2, 1, 2, 1]
    assert scores[0]["ab"]["yes_token_logits"] == {"1": 8.0}


def test_portable_cli_round_trip(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    entries = []
    for cid in ("fake-one", "fake-two"):
        f = bundle / (cid + ".json")
        atomic_json(f, case(cid))
        entries.append(
            dict(case_id=cid, file=f.name, sha256=file_hash(f), nodes=8, pairs=28)
        )
    atomic_json(
        bundle / "manifest.json",
        dict(version="atom-bundle-v1", complete=True, test_data=True, cases=entries),
    )
    out = tmp_path / "results"
    config = ROOT / "configs/matching/random-smoke.yaml"

    def cli(*args):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "clinical_factflow.server_matching",
                *map(str, args),
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr

    cli("run", "--bundle", bundle, "--out", out, "--config", config, "--max-batches", 1)
    cli("run", "--bundle", bundle, "--out", out, "--config", config)
    assert json.loads((out / "index.json").read_text())["complete"]
    cli(
        "relabel",
        "--results",
        out,
        "--name",
        "wide",
        "--blocker-threshold",
        0,
        "--top-k",
        99,
    )
    cli("score", "--results", out, "--policy", "wide", "--config", config)
    cli(
        "review",
        "--results",
        out,
        "--policy",
        "wide",
        "--out",
        tmp_path / "review",
        "--blocker-band",
        1,
        "--nli-band",
        100,
    )
    cli(
        "rejudge",
        "--results",
        out,
        "--policy",
        "wide",
        "--name",
        "second",
        "--pairs",
        tmp_path / "review",
        "--config",
        config,
    )
    cli(
        "rejudge",
        "--results",
        out,
        "--policy",
        "wide",
        "--name",
        "second",
        "--pairs",
        tmp_path / "review",
        "--config",
        config,
    )
    cli("export", "--results", out, "--policy", "second", "--out", tmp_path / "export")
    rows = [
        json.loads(l)
        for f in (tmp_path / "export").glob("*.jsonl")
        for l in f.read_text().splitlines()
    ]
    assert len(rows) == 56 and all(
        r["test_data"] and r["status"] == "complete" for r in rows
    )


def test_policy_creation_resumes_but_rejects_changed_settings(tmp_path):
    db = ledger(tmp_path)
    create_policy(db, "initial", 0.4, 4, 5.28, scorer_hash(CFG))
    assert db.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == 28
    with pytest.raises(ValueError, match="different settings"):
        create_policy(db, "initial", 0.5, 4, 5.28, scorer_hash(CFG))


def test_selective_review_inherits_the_specified_parent_not_latest_other_review(
    tmp_path,
):
    db = ledger(tmp_path)
    scorer = Counting()
    score_policy(db, "initial", scorer, 7)
    ids = [
        r[0]
        for r in db.execute(
            "SELECT pair_id FROM annotations WHERE judgment_id IS NOT NULL LIMIT 2"
        )
    ]
    create_policy(db, "review-one", 0.4, 4, 5.28, scorer_hash(CFG), "initial", [ids[0]])
    score_policy(db, "review-one", scorer, 7)
    create_policy(db, "review-two", 0.4, 4, 5.28, scorer_hash(CFG), "initial", [ids[1]])

    def jid(policy, pair):
        return db.execute(
            "SELECT judgment_id FROM annotations WHERE policy=? AND pair_id=?",
            (policy, pair),
        ).fetchone()[0]

    assert jid("review-one", ids[0]) != jid("initial", ids[0])
    assert jid("review-two", ids[0]) == jid("initial", ids[0])
    create_policy(
        db,
        "review-no-selection",
        0.4,
        4,
        5.28,
        scorer_hash(CFG),
        "initial",
        [],
        review=True,
    )
    assert summary(db, "review-no-selection")["complete"]
    assert jid("review-no-selection", ids[0]) == jid("initial", ids[0])


def test_interrupted_geometry_is_archived_and_rebuilt(tmp_path):
    (tmp_path / "x.building.sqlite").write_bytes(b"partial scratch build")
    db = ledger(tmp_path)
    assert summary(db, "initial")["pair_universe"] == 28
    saved = list((tmp_path / "interrupted-builds").glob("*/x.building.sqlite"))
    assert len(saved) == 1 and saved[0].read_bytes() == b"partial scratch build"


def test_blocker_profiler_saves_production_values_and_resumes_without_encoding(
    tmp_path, monkeypatch
):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "profile_blocker", ROOT / "scripts/profile_blocker.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    c = case()
    f = bundle / "case.json"
    atomic_json(f, c)
    atomic_json(
        bundle / "manifest.json",
        dict(
            version="atom-bundle-v1",
            complete=True,
            completed_records=1,
            expected_records=1,
            cases=[
                dict(
                    case_id=c["case_id"],
                    file=f.name,
                    sha256=file_hash(f),
                    nodes=8,
                    pairs=28,
                )
            ],
        ),
    )
    out = tmp_path / "profile"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "profile",
            "--bundle",
            str(bundle),
            "--out",
            str(out),
            "--config",
            str(ROOT / "configs/matching/random-smoke.yaml"),
        ],
    )
    module.main()
    summary = json.loads((out / "summary.json").read_text())
    assert summary["total_pairs"] == 28 and summary["per_trace_default_mean"] is None
    arr = np.load(next(out.glob("*/pairs.npz")))["pairs"]
    expected = list(
        geometry(
            c["nodes"],
            RandomEncoder(1729, 24).encode([n["logic_text"] for n in c["nodes"]]),
        )
    )
    for row, other in zip(arr, expected):
        assert list(row) == list(other[1:])
    count = int(
        np.count_nonzero(
            (arr["combined"] >= 0.62) & (np.minimum(arr["rank_a"], arr["rank_b"]) <= 12)
        )
    )
    default = next(
        p for p in summary["policies"] if p["threshold"] == 0.62 and p["top_k"] == 12
    )
    assert default["candidate_pairs"] == count
    assert default["gpu_hours"] == pytest.approx(count / 7.25 / 3600)
    monkeypatch.setattr(
        module, "get_encoder", lambda *a: pytest.fail("Must reuse frozen saved scores")
    )
    module.main()
