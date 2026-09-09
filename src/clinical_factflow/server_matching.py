"""Portable all-pair annotation ledger. Blocker UNRELATED is a final label, not absence."""

from __future__ import annotations
import argparse, fcntl, json, math, os, sqlite3, tarfile, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import yaml
from .config import Matching, digest, UniqueLoader
from .io import atomic_json, file_hash
from .matching import tokenize, relation
from .pair_backends import BGEEncoder, RandomEncoder, RandomLogitScorer, QwenLogitScorer
from .resumable_extraction import sealed_read


def scorer_hash(config):
    return digest({"scorer": config["scorer"], "batch_size": config["batch_size"]})


def stamp():
    return datetime.now(timezone.utc).isoformat()


def dump(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, allow_nan=False)


def putmeta(db, key, value):
    db.execute("INSERT OR REPLACE INTO metadata VALUES (?,?)", (key, dump(value)))


def meta(db, key):
    row = db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def export_bundle(extraction, out, allow_partial=False):
    extraction, out = Path(extraction), Path(out)
    manifest = sealed_read(extraction / "manifest.json")
    if out.exists() or out.with_suffix(".tar.gz").exists():
        raise FileExistsError(out)
    available = [
        t
        for t in manifest["tasks"]
        if (extraction / "results" / (t["id"] + ".json")).exists()
    ]
    if len(available) != len(manifest["tasks"]) and not allow_partial:
        raise ValueError(
            "Extraction incomplete; --allow-partial is for an explicitly marked diagnostic snapshot only"
        )
    cases = defaultdict(dict)
    records = []
    for t in available:
        f = extraction / "results" / (t["id"] + ".json")
        saved = sealed_read(f)
        r = saved["result"]
        if saved["task_hash"] != digest(t) or r["record_hash"] != digest(t["record"]):
            raise ValueError("Extraction record changed")
        records.append({"task_id": t["id"], "sha256": file_hash(f)})
        cid = t["record"]["provenance"]["case_id"]
        cases[cid]  # retain cases with explicit empty extractions
        for m in r["mentions"]:
            qualifiers = sorted(set(m["qualifiers"]))
            nid = digest([cid, m["text"], qualifiers])
            if nid not in cases[cid]:
                cases[cid][nid] = {
                    "id": nid,
                    "text": m["text"],
                    "qualifiers": qualifiers,
                    "logic_text": m["text"]
                    + ("\nQualifiers: " + "; ".join(qualifiers) if qualifiers else ""),
                    "mentions": [],
                }
            cases[cid][nid]["mentions"].append(
                {"task_id": t["id"], "mention": m, "bindings": t["bindings"]}
            )
    out.mkdir(parents=True, exist_ok=False)
    entries = []
    for cid, nodes in sorted(cases.items()):
        name = "cases/" + digest(cid)[:24] + ".json"
        atoms = sorted(nodes.values(), key=lambda n: n["id"])
        atomic_json(out / name, {"case_id": cid, "nodes": atoms})
        entries.append(
            {
                "case_id": cid,
                "file": name,
                "sha256": file_hash(out / name),
                "nodes": len(atoms),
                "pairs": len(atoms) * (len(atoms) - 1) // 2,
            }
        )
    doc = {
        "version": "atom-bundle-v1",
        "complete": len(available) == len(manifest["tasks"]),
        "test_data": False,
        "node_identity": "case + exact text + qualifier set; occurrence annotations retained",
        "pair_scope": "all unordered distinct-node pairs within the same case, across all conditions",
        "completed_records": len(available),
        "expected_records": len(manifest["tasks"]),
        "extraction_manifest_hash": file_hash(extraction / "manifest.json"),
        "records": records,
        "cases": entries,
    }
    atomic_json(out / "manifest.json", doc)
    archive = out.with_suffix(".tar.gz")
    if archive.exists():
        raise FileExistsError(archive)
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(out, arcname=out.name)
    return doc


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    return db


SCHEMA = """
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE nodes(idx INTEGER PRIMARY KEY,node_id TEXT UNIQUE NOT NULL,logic_text TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE pairs(pair_id TEXT PRIMARY KEY,a INTEGER NOT NULL,b INTEGER NOT NULL,cosine REAL NOT NULL,lexical REAL NOT NULL,token_intersection INTEGER NOT NULL,a_token_count INTEGER NOT NULL,b_token_count INTEGER NOT NULL,combined REAL NOT NULL,rank_a INTEGER NOT NULL,rank_b INTEGER NOT NULL,UNIQUE(a,b));
CREATE TABLE judgments(id INTEGER PRIMARY KEY,pair_id TEXT NOT NULL REFERENCES pairs(pair_id),scorer_hash TEXT NOT NULL,round_id TEXT NOT NULL,ab_margin REAL NOT NULL,ba_margin REAL NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(pair_id,scorer_hash,round_id));
CREATE INDEX judgment_lookup ON judgments(pair_id,scorer_hash,id);
CREATE TABLE policies(name TEXT PRIMARY KEY,blocker_threshold REAL NOT NULL,top_k INTEGER NOT NULL,nli_threshold REAL NOT NULL,scorer_hash TEXT NOT NULL,parent TEXT,created_at TEXT NOT NULL);
CREATE TABLE annotations(policy TEXT NOT NULL REFERENCES policies(name),pair_id TEXT NOT NULL REFERENCES pairs(pair_id),relation TEXT CHECK(relation IN ('UNRELATED','EQUIVALENT','A_ENTAILS_B','B_ENTAILS_A')),decision_stage TEXT NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL,judgment_id INTEGER REFERENCES judgments(id),forced INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(policy,pair_id));
CREATE INDEX pending_annotations ON annotations(policy,status);
CREATE TABLE attempts(id INTEGER PRIMARY KEY,policy TEXT,round_id TEXT,pair_ids TEXT,status TEXT,error_type TEXT,created_at TEXT NOT NULL);
"""


def geometry(nodes, embeddings):
    n = len(nodes)
    emb = np.asarray(embeddings, dtype=np.float64)
    if emb.ndim != 2 or len(emb) != n or not np.isfinite(emb).all():
        raise ValueError("Invalid embeddings")
    norm = np.linalg.norm(emb, axis=1, keepdims=True)
    if (norm == 0).any():
        raise ValueError("Zero embedding")
    emb = emb / norm
    cos = np.clip(emb @ emb.T, -1, 1)
    tokens = [tokenize(x["logic_text"]) for x in nodes]
    lex = np.zeros((n, n))
    overlap = np.zeros((n, n), dtype=np.int32)
    for i in range(n):
        for j in range(i + 1, n):
            count = len(tokens[i] & tokens[j])
            den = min(len(tokens[i]), len(tokens[j]))
            overlap[i, j] = overlap[j, i] = count
            lex[i, j] = lex[j, i] = count / den if den else 0.0
    combined = np.maximum(cos, lex)
    ranks = np.zeros((n, n), dtype=np.int32)
    for i in range(n):
        ordered = sorted(
            (j for j in range(n) if j != i), key=lambda j: (-combined[i, j], j)
        )
        for rank, j in enumerate(ordered, 1):
            ranks[i, j] = rank

    def rows():
        for a in range(n):
            for b in range(a + 1, n):
                yield (
                    digest([nodes[a]["id"], nodes[b]["id"]]),
                    a,
                    b,
                    float(cos[a, b]),
                    float(lex[a, b]),
                    int(overlap[a, b]),
                    len(tokens[a]),
                    len(tokens[b]),
                    float(combined[a, b]),
                    int(ranks[a, b]),
                    int(ranks[b, a]),
                )

    return rows()


def init_case(path, case, encoder, config, input_hash):
    path = Path(path)
    code = {
        n: file_hash(Path(__file__).parent / n)
        for n in ["server_matching.py", "pair_backends.py", "matching.py"]
    }
    signature = {
        "input_hash": input_hash,
        "encoder_config": config["encoder"],
        "scorer_config": config["scorer"],
        "batch_size": config["batch_size"],
        "initial_policy": config["policy"],
        "bundle": case.get("bundle_provenance", {}),
        "code_hashes": code,
    }
    if path.exists():
        db = connect(path)
        if meta(db, "signature") != signature:
            db.close()
            raise ValueError(
                "Matching input/model/code changed; preserve the old ledger and use a new output"
            )
        if meta(db, "geometry_complete"):
            return db
        db.close()
        raise ValueError(
            "Uncommitted geometry file; preserve it for audit and rebuild in a new output"
        )
    temp = path.with_suffix(".building.sqlite")
    if temp.exists():
        archive = path.parent / "interrupted-builds" / str(time.time_ns())
        archive.mkdir(parents=True)
        for old in (temp, Path(str(temp) + "-wal"), Path(str(temp) + "-shm")):
            if old.exists():
                os.replace(old, archive / old.name)
    db = connect(temp)
    db.executescript(SCHEMA)
    nodes = case["nodes"]
    texts = [x["logic_text"] for x in nodes]
    emb = encoder.encode(texts) if texts else np.zeros((0, 1))
    with db:
        putmeta(db, "signature", signature)
        putmeta(db, "case_id", case["case_id"])
        putmeta(
            db,
            "test_data",
            case.get("test_data", False)
            or config["encoder"]["backend"] == "random_mock"
            or config["scorer"]["backend"] == "random_mock",
        )
        putmeta(db, "bundle", case.get("bundle_provenance", {}))
        putmeta(db, "encoder", encoder.metadata)
        putmeta(db, "config", config)
        putmeta(db, "pair_scope", "all distinct node pairs within this case")
        db.executemany(
            "INSERT INTO nodes VALUES (?,?,?,?)",
            ((i, n["id"], n["logic_text"], dump(n)) for i, n in enumerate(nodes)),
        )
        db.executemany(
            "INSERT INTO pairs VALUES (?,?,?,?,?,?,?,?,?,?,?)", geometry(nodes, emb)
        )
        putmeta(db, "geometry_complete", True)
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    os.replace(temp, path)
    return connect(path)


def create_policy(
    db,
    name,
    blocker_threshold,
    top_k,
    nli_threshold,
    scorer_hash,
    parent=None,
    force_ids=(),
):
    if (
        not all(math.isfinite(float(x)) for x in (blocker_threshold, nli_threshold))
        or not 0 <= blocker_threshold <= 1
        or type(top_k) is not int
        or top_k < 1
    ):
        raise ValueError("Invalid thresholds")
    force = set(force_ids)
    if force and any(
        not db.execute("SELECT 1 FROM pairs WHERE pair_id=?", (i,)).fetchone()
        for i in force
    ):
        raise ValueError("Unknown forced pair")
    with db:
        db.execute(
            "INSERT INTO policies VALUES (?,?,?,?,?,?,?)",
            (
                name,
                blocker_threshold,
                top_k,
                nli_threshold,
                scorer_hash,
                parent,
                stamp(),
            ),
        )
        cur = db.execute("SELECT * FROM pairs ORDER BY a,b")

        def rows():
            for p in cur:
                candidate = (
                    p["combined"] >= blocker_threshold
                    and min(p["rank_a"], p["rank_b"]) <= top_k
                )
                forced = p["pair_id"] in force
                if not candidate and not forced:
                    why = (
                        "below_threshold"
                        if p["combined"] < blocker_threshold
                        else "outside_both_top_k"
                    )
                    yield (
                        name,
                        p["pair_id"],
                        "UNRELATED",
                        "blocker",
                        "complete",
                        why,
                        None,
                        0,
                    )
                else:
                    old = db.execute(
                        "SELECT * FROM judgments WHERE pair_id=? AND scorer_hash=? ORDER BY id DESC LIMIT 1",
                        (p["pair_id"], scorer_hash),
                    ).fetchone()
                    if old and not forced:
                        yield (
                            name,
                            p["pair_id"],
                            relation(old["ab_margin"], old["ba_margin"], nli_threshold),
                            "nli",
                            "complete",
                            "stored_scores",
                            old["id"],
                            0,
                        )
                    else:
                        yield (
                            name,
                            p["pair_id"],
                            None,
                            "nli_review" if forced else "nli",
                            "pending",
                            "requested_review" if forced else "needs_model",
                            None,
                            int(forced),
                        )

        db.executemany("INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?)", rows())


def validate_scores(items, pairs):
    ids = [x.get("pair_id") for x in items]
    if len(ids) != len(set(ids)) or set(ids) != {x["pair_id"] for x in pairs}:
        raise ValueError("Model omitted/duplicated a pair")
    for x in items:
        for direction in ["ab", "ba"]:
            d = x[direction]
            if not all(
                type(d[k]) in (float, int) and math.isfinite(d[k])
                for k in [
                    "margin",
                    "yes_logprob_mass",
                    "no_logprob_mass",
                    "log_normalizer",
                    "conditional_yes_probability",
                ]
            ):
                raise ValueError("Non-finite/missing directional score")
            if not math.isclose(
                d["margin"], d["yes_logprob_mass"] - d["no_logprob_mass"], abs_tol=1e-4
            ):
                raise ValueError("Margin does not match saved YES/NO masses")
            if not 0 <= d["conditional_yes_probability"] <= 1:
                raise ValueError("Invalid conditional probability")
            for key in ["yes_token_logits", "no_token_logits"]:
                if not d[key] or not all(
                    math.isfinite(float(v)) for v in d[key].values()
                ):
                    raise ValueError("Invalid token logits")
                mass = (
                    float(np.logaddexp.reduce(list(d[key].values())))
                    - d["log_normalizer"]
                )
                expected = d[
                    (
                        "yes_logprob_mass"
                        if key == "yes_token_logits"
                        else "no_logprob_mass"
                    )
                ]
                if not math.isclose(mass, expected, abs_tol=1e-4):
                    raise ValueError("Log probability does not match saved logits")
            prob = math.exp(-float(np.logaddexp(0, -d["margin"])))
            if not math.isclose(prob, d["conditional_yes_probability"], abs_tol=1e-5):
                raise ValueError("Probability does not match margin")
    return {x["pair_id"]: x for x in items}


def score_policy(db, name, scorer, batch_size=16, max_batches=None):
    policy = db.execute("SELECT * FROM policies WHERE name=?", (name,)).fetchone()
    if policy is None:
        raise ValueError("Unknown policy")
    stored = meta(db, "scorer_runtime:" + policy["scorer_hash"])
    stable = {
        k: v
        for k, v in scorer.metadata.items()
        if k not in ["effective_batch_sizes", "last_token_only_forward"]
    }
    if stored and stored != stable:
        raise ValueError("Resolved model/tokenizer changed")
    with db:
        putmeta(db, "scorer_runtime:" + policy["scorer_hash"], stable)
    batches = 0
    while max_batches is None or batches < max_batches:
        rows = db.execute(
            """SELECT p.pair_id,na.logic_text a_text,nb.logic_text b_text,a.forced FROM annotations a JOIN pairs p ON p.pair_id=a.pair_id JOIN nodes na ON na.idx=p.a JOIN nodes nb ON nb.idx=p.b WHERE a.policy=? AND a.relation IS NULL ORDER BY p.a,p.b LIMIT ?""",
            (name, batch_size),
        ).fetchall()
        if not rows:
            break
        pairs = [dict(r) for r in rows]
        round_id = "review:" + name if any(r["forced"] for r in rows) else "initial"
        with db:
            attempt = db.execute(
                "INSERT INTO attempts(policy,round_id,pair_ids,status,created_at) VALUES (?,?,?,?,?)",
                (
                    name,
                    round_id,
                    dump([p["pair_id"] for p in pairs]),
                    "running",
                    stamp(),
                ),
            ).lastrowid
        try:
            got = validate_scores(scorer.score(pairs, round_id=round_id), pairs)
            with db:
                for p in pairs:
                    x = got[p["pair_id"]]
                    ab = x["ab"]["margin"]
                    ba = x["ba"]["margin"]
                    # A fresh review has a new round id; previous values are never overwritten.
                    db.execute(
                        "INSERT INTO judgments(pair_id,scorer_hash,round_id,ab_margin,ba_margin,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (
                            p["pair_id"],
                            policy["scorer_hash"],
                            round_id,
                            ab,
                            ba,
                            dump(x),
                            stamp(),
                        ),
                    )
                    jid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                    db.execute(
                        "UPDATE annotations SET relation=?,status=?,judgment_id=?,reason=? WHERE policy=? AND pair_id=?",
                        (
                            relation(ab, ba, policy["nli_threshold"]),
                            "complete",
                            jid,
                            "model_scores",
                            name,
                            p["pair_id"],
                        ),
                    )
                db.execute(
                    "UPDATE attempts SET status=? WHERE id=?", ("complete", attempt)
                )
                putmeta(db, "last_model_metadata", scorer.metadata)
        except Exception as exc:
            with db:
                db.execute(
                    "UPDATE attempts SET status=?,error_type=? WHERE id=?",
                    ("failed", type(exc).__name__, attempt),
                )
            raise
        batches += 1
    return summary(db, name)


def summary(db, policy):
    n = db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM pairs").fetchone()[0]
    groups = [
        dict(r)
        for r in db.execute(
            "SELECT decision_stage,relation,status,COUNT(*) count FROM annotations WHERE policy=? GROUP BY decision_stage,relation,status",
            (policy,),
        )
    ]
    if total != n * (n - 1) // 2 or sum(x["count"] for x in groups) != total:
        raise ValueError("Pair-universe coverage mismatch")
    return {
        "case_id": meta(db, "case_id"),
        "policy": policy,
        "test_data": meta(db, "test_data"),
        "input_complete": (meta(db, "bundle") or {}).get("complete", True),
        "nodes": n,
        "pair_universe": total,
        "complete": all(x["status"] == "complete" for x in groups),
        "groups": groups,
    }


def export_rows(db, policy, path, blocker_band=None, nli_band=None, topk_band=1):
    pol = db.execute("SELECT * FROM policies WHERE name=?", (policy,)).fetchone()
    if pol is None:
        raise ValueError("Unknown policy")
    sql = """SELECT p.*,a.relation,a.decision_stage,a.status,a.reason,a.judgment_id,a.forced,j.ab_margin,j.ba_margin,j.payload judgment,na.node_id a_node_id,nb.node_id b_node_id,na.logic_text a_text,nb.logic_text b_text FROM annotations a JOIN pairs p ON p.pair_id=a.pair_id JOIN nodes na ON na.idx=p.a JOIN nodes nb ON nb.idx=p.b LEFT JOIN judgments j ON j.id=a.judgment_id WHERE a.policy=? ORDER BY p.a,p.b"""
    count = 0
    case_id = meta(db, "case_id")
    test_data = meta(db, "test_data")
    bundle = meta(db, "bundle") or {}
    with Path(path).open("w") as f:
        for row in db.execute(sql, (policy,)):
            d = dict(row)
            reasons = []
            if (
                blocker_band is not None
                and abs(d["combined"] - pol["blocker_threshold"]) <= blocker_band
            ):
                reasons.append("blocker_threshold")
            if nli_band is not None and any(
                d[k] is not None and abs(d[k] - pol["nli_threshold"]) <= nli_band
                for k in ["ab_margin", "ba_margin"]
            ):
                reasons.append("nli_threshold")
            if (
                blocker_band is not None
                and abs(min(d["rank_a"], d["rank_b"]) - pol["top_k"]) <= topk_band
            ):
                reasons.append("top_k_boundary")
            if (blocker_band is not None or nli_band is not None) and not reasons:
                continue
            d.update(
                case_id=case_id,
                policy=policy,
                test_data=test_data,
                review_reasons=reasons,
                thresholds=dict(pol),
                input_complete=bundle.get("complete", True),
            )
            if d["judgment"]:
                d["judgment"] = json.loads(d["judgment"])
            f.write(dump(d) + "\n")
            count += 1
    return count


def load_config(path):
    cfg = yaml.load(Path(path).read_text(), Loader=UniqueLoader)
    if cfg.get("version") != "pair-labeling-v1":
        raise ValueError("Unknown matching config version")
    if cfg["encoder"]["backend"] not in ("random_mock", "sentence_transformer") or cfg[
        "scorer"
    ]["backend"] not in ("random_mock", "local_qwen"):
        raise ValueError("Unknown local/test backend")
    if cfg["batch_size"] < 1:
        raise ValueError("Invalid batch size")
    return cfg


def get_encoder(cfg):
    return (
        RandomEncoder(cfg.get("seed", 42), cfg.get("dimensions", 24))
        if cfg["backend"] == "random_mock"
        else BGEEncoder(cfg)
    )


def get_scorer(cfg):
    if cfg["scorer"]["backend"] == "random_mock":
        return RandomLogitScorer(cfg["scorer"].get("seed", 42))
    s = {**cfg["scorer"]}
    s.pop("backend")
    s.pop("seed", None)
    # Reuse the production local model's existing validated settings model.
    return QwenLogitScorer(
        Matching.model_validate(
            {
                **s,
                "backend": "local_qwen",
                "batch_size": cfg["batch_size"],
                "blocker_model": cfg["encoder"]["model"],
                "blocker_revision": cfg["encoder"]["revision"],
                "blocker_threshold": cfg["policy"]["blocker_threshold"],
                "blocker_top_k": cfg["policy"]["top_k"],
                "blocker_metric": "max_cosine_containment",
                "entailment_threshold": cfg["policy"]["nli_threshold"],
                "threshold_provenance": "Inherited, not clinically calibrated",
                "cluster_policy": "complete_link",
                "max_parallel": 1,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("bundle")
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--allow-partial", action="store_true")
    p = sub.add_parser("run")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--allow-partial", action="store_true")
    p.add_argument("--max-batches", type=int)
    for command in ["score", "relabel", "export", "review", "rejudge"]:
        p = sub.add_parser(command)
        p.add_argument("--results", type=Path, required=True)
        p.add_argument("--policy", default="initial")
        if command in ["score", "rejudge"]:
            p.add_argument("--config", type=Path, required=True)
        if command in ["relabel", "rejudge"]:
            p.add_argument("--name", required=True)
        if command == "relabel":
            p.add_argument("--blocker-threshold", type=float)
            p.add_argument("--top-k", type=int)
            p.add_argument("--nli-threshold", type=float)
        if command in ["export", "review"]:
            p.add_argument("--out", type=Path, required=True)
        if command == "review":
            p.add_argument("--blocker-band", type=float, default=0.02)
            p.add_argument("--nli-band", type=float, default=0.5)
        if command == "rejudge":
            p.add_argument("--pairs", type=Path, required=True)
    args = parser.parse_args()
    if args.cmd == "bundle":
        print(dump(export_bundle(args.extraction, args.out, args.allow_partial)))
        return
    target = args.out if args.cmd == "run" else args.results
    target.mkdir(parents=True, exist_ok=True)
    lock = (target / "matching.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    scorer = None
    if args.cmd == "run":
        cfg = load_config(args.config)
        bundle = json.loads((args.bundle / "manifest.json").read_text())
        if bundle.get("version") != "atom-bundle-v1":
            raise ValueError("Unknown bundle version")
        if not bundle["complete"] and not args.allow_partial:
            raise ValueError("Partial bundle requires explicit --allow-partial")
        encoder = get_encoder(cfg["encoder"])
        reports = []
        for entry in bundle["cases"]:
            f = args.bundle / entry["file"]
            if file_hash(f) != entry["sha256"]:
                raise ValueError("Bundle changed")
            case = json.loads(f.read_text())
            if (
                case["case_id"] != entry["case_id"]
                or len(case["nodes"]) != entry["nodes"]
                or entry["pairs"] != len(case["nodes"]) * (len(case["nodes"]) - 1) // 2
            ):
                raise ValueError("Bundle inventory mismatch")
            case["bundle_provenance"] = {
                "manifest_sha256": file_hash(args.bundle / "manifest.json"),
                "complete": bundle["complete"],
                "test_data": bundle.get("test_data", False),
            }
            case["test_data"] = case.get("test_data", False) or bundle.get(
                "test_data", False
            )
            db = init_case(
                target / (digest(case["case_id"])[:24] + ".sqlite"),
                case,
                encoder,
                cfg,
                entry["sha256"],
            )
            if not db.execute(
                "SELECT 1 FROM policies WHERE name=?", ("initial",)
            ).fetchone():
                create_policy(
                    db, "initial", **cfg["policy"], scorer_hash=scorer_hash(cfg)
                )
            if not summary(db, "initial")["complete"]:
                if scorer is None:
                    scorer = get_scorer(cfg)
                score_policy(db, "initial", scorer, cfg["batch_size"], args.max_batches)
            report = summary(db, "initial")
            reports.append(report)
            print(dump(report), flush=True)
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            db.close()
        atomic_json(
            target / "index.json",
            {
                "complete": all(x["complete"] for x in reports),
                "input_complete": bundle["complete"],
                "config": cfg,
                "cases": reports,
            },
        )
        return
    cfg = load_config(args.config) if hasattr(args, "config") else None
    reviews = defaultdict(set)
    if args.cmd == "rejudge":
        paths = (
            sorted(args.pairs.glob("*.jsonl")) if args.pairs.is_dir() else [args.pairs]
        )
        if not paths:
            raise ValueError("No review files")
        for path in paths:
            with path.open() as stream:
                for line in stream:
                    x = json.loads(line)
                    reviews[x["case_id"]].add(x["pair_id"])
    if args.cmd in ["export", "review"]:
        args.out.mkdir(parents=True, exist_ok=False)
    reports = []
    files = [
        f
        for f in sorted(target.glob("*.sqlite"))
        if not f.name.endswith(".building.sqlite")
    ]
    if not files:
        raise ValueError("No matching ledgers")
    known_cases = set()
    for f in files:
        check = connect(f)
        known_cases.add(meta(check, "case_id"))
        check.close()
    if set(reviews) - known_cases:
        raise ValueError("Review refers to an unknown case")
    for f in files:
        db = connect(f)
        pol = db.execute(
            "SELECT * FROM policies WHERE name=?", (args.policy,)
        ).fetchone()
        if pol is None:
            raise ValueError("Unknown policy")
        name = args.policy
        if args.cmd == "relabel":
            create_policy(
                db,
                args.name,
                (
                    args.blocker_threshold
                    if args.blocker_threshold is not None
                    else pol["blocker_threshold"]
                ),
                args.top_k if args.top_k is not None else pol["top_k"],
                (
                    args.nli_threshold
                    if args.nli_threshold is not None
                    else pol["nli_threshold"]
                ),
                pol["scorer_hash"],
                args.policy,
            )
            name = args.name
        elif args.cmd in ["score", "rejudge"]:
            if scorer_hash(cfg) != pol["scorer_hash"]:
                raise ValueError(
                    "Different model settings require a separately versioned scoring study"
                )
            signature = meta(db, "signature")
            code = {
                n: file_hash(Path(__file__).parent / n)
                for n in signature["code_hashes"]
            }
            if code != signature["code_hashes"]:
                raise ValueError(
                    "Scoring implementation changed; preserve the old ledger and use a new output"
                )
            if args.cmd == "rejudge":
                ids = reviews[meta(db, "case_id")]
                if any(
                    not db.execute(
                        "SELECT 1 FROM pairs WHERE pair_id=?", (i,)
                    ).fetchone()
                    for i in ids
                ):
                    raise ValueError("Review refers to an unknown pair")
                existing = db.execute(
                    "SELECT * FROM policies WHERE name=?", (args.name,)
                ).fetchone()
                if not existing:
                    create_policy(
                        db,
                        args.name,
                        pol["blocker_threshold"],
                        pol["top_k"],
                        pol["nli_threshold"],
                        pol["scorer_hash"],
                        args.policy,
                        ids,
                    )
                else:
                    old_ids = {
                        r[0]
                        for r in db.execute(
                            "SELECT pair_id FROM annotations WHERE policy=? AND forced=1",
                            (args.name,),
                        )
                    }
                    if existing["parent"] != args.policy or old_ids != ids:
                        raise ValueError(
                            "Review selection changed; choose a new policy name"
                        )
                name = args.name
            if not summary(db, name)["complete"]:
                if scorer is None:
                    scorer = get_scorer(cfg)
                score_policy(db, name, scorer, cfg["batch_size"])
        elif args.cmd in ["export", "review"]:
            count = export_rows(
                db,
                name,
                args.out / (f.stem + ".jsonl"),
                args.blocker_band if args.cmd == "review" else None,
                args.nli_band if args.cmd == "review" else None,
            )
            print(dump({"file": f.name, "rows": count}))
        reports.append(summary(db, name))
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.close()
    atomic_json(
        target
        / ("policy-" + (args.name if hasattr(args, "name") else args.policy) + ".json"),
        {"cases": reports},
    )
    print(dump(reports))


if __name__ == "__main__":
    main()
