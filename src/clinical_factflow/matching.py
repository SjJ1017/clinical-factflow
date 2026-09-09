"""Two directional Qwen entailment scores; local inference only."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
from .config import digest
from .io import atomic_json, file_hash, verify_run
from .runner import environment


def tokenize(text):
    out = set()
    for token in re.findall(r"[a-z0-9][a-z0-9.%/-]*", text.lower()):
        if not any(c.isdigit() for c in token):
            for suffix in ("ing", "ed", "es", "s"):
                if len(token) > len(suffix) + 2 and token.endswith(suffix):
                    token = token[:-len(suffix)]
                    break
        out.add(token)
    return out


def candidates(texts, embeddings, threshold, top_k):
    tokens = [tokenize(t) for t in texts]
    found = {}
    for i in range(len(texts)):
        cosine = embeddings[i] @ embeddings.T
        scored = []
        for j in range(len(texts)):
            if i == j:
                continue
            denom = min(len(tokens[i]), len(tokens[j]))
            containment = len(tokens[i] & tokens[j]) / denom if denom else 0.0
            s = max(float(cosine[j]), containment)
            if s >= threshold:
                scored.append((s,j))
        for s,j in sorted(scored, key=lambda x: (-x[0],x[1]))[:top_k]:
            found[tuple(sorted((i,j)))] = s
    return [(a,b,s) for (a,b),s in sorted(found.items())]


def relation(ab, ba, threshold):
    if not all(math.isfinite(x) for x in (ab,ba)):
        raise ValueError("Non-finite NLI scores cannot become UNRELATED")
    return {(True,True): "EQUIVALENT", (True,False): "A_ENTAILS_B",
            (False,True): "B_ENTAILS_A", (False,False): "UNRELATED"}[(ab >= threshold, ba >= threshold)]


def complete_link_groups(n, labels):
    groups = []
    for i in range(n):
        for g in groups:
            if all(labels.get(tuple(sorted((i,j)))) == "EQUIVALENT" for j in g):
                g.append(i)
                break
        else:
            groups.append([i])
    return groups


def answer_ids(tok):
    ids = {}
    for word in ("YES", "NO"):
        ids[word] = {tok.encode(v, add_special_tokens=False)[0] for v in
                     (word, " "+word, word.capitalize(), word.lower(), " "+word.capitalize(), " "+word.lower())}
    both = ids["YES"] & ids["NO"]
    ids = {k: sorted(v - both) for k,v in ids.items()}
    if not all(ids.values()):
        raise ValueError("Tokenizer does not separate YES/NO first tokens")
    return ids


class LocalQwen:
    def __init__(self, cfg):
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        self.cfg = cfg
        self.tok = AutoTokenizer.from_pretrained(cfg.model, revision=cfg.revision,
            padding_side="left", local_files_only=cfg.local_files_only)
        if self.tok.pad_token_id is None:
            self.tok.pad_token = self.tok.eos_token
        kw = {"torch_dtype": getattr(torch, cfg.dtype), "device_map": cfg.device,
              "attn_implementation": "eager", "local_files_only": cfg.local_files_only,
              "revision": cfg.revision}
        if cfg.load_4bit:
            kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True,
                bnb_4bit_compute_dtype=getattr(torch,cfg.dtype), bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
        self.net = AutoModelForCausalLM.from_pretrained(cfg.model, **kw).eval()
        self.ids = answer_ids(self.tok)
        self.metadata = {"model": cfg.model, "requested_revision": cfg.revision,
                         "resolved_revision": getattr(self.net.config, "_commit_hash", None),
                         "yes_no_token_ids": self.ids, "effective_batch_sizes": []}

    def margins(self, pairs):
        import torch
        cfg = self.cfg
        prompts = [self.tok.apply_chat_template([
            {"role": "system", "content": cfg.system_prompt},
            {"role": "user", "content": cfg.user_template.format(a=a,b=b)}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False) for a,b in pairs]
        # No truncation: dropping the end of a fact invalidates entailment.
        scores, i, batch = [], 0, cfg.batch_size
        while i < len(prompts):
            enc = self.tok(prompts[i:i+batch], return_tensors="pt", padding=True,
                           add_special_tokens=False, truncation=False).to(self.net.device)
            if enc["input_ids"].shape[-1] > self.net.config.max_position_embeddings:
                raise ValueError("NLI prompt exceeds model context length")
            try:
                with torch.inference_mode():
                    logits = self.net(**enc).logits[:, -1, :].float()
                lp = torch.log_softmax(logits, dim=-1)
                y = torch.logsumexp(lp[:,self.ids["YES"]],dim=-1)
                n = torch.logsumexp(lp[:,self.ids["NO"]],dim=-1)
                values = (y-n).tolist()
                if not all(math.isfinite(x) for x in values):
                    raise ValueError("Non-finite model margins")
            except torch.OutOfMemoryError:
                del enc
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                if batch == 1:
                    raise
                batch = max(1,batch//2)
                continue
            self.metadata["effective_batch_sizes"].append(len(values))
            scores.extend(values)
            i += len(values)
        return scores

    def score(self, pairs):
        return list(zip(self.margins(pairs), self.margins([(b,a) for a,b in pairs])))


def match_mentions(mentions, cfg, encode, score):
    # Never compare different patients. Repeat text is one node with all mentions retained.
    texts = sorted({m["text"] for m in mentions})
    if len(texts) > 1:
        emb = np.asarray(encode(texts), dtype=float)
        if emb.ndim != 2 or len(emb) != len(texts) or not np.isfinite(emb).all():
            raise ValueError("Invalid blocker embeddings")
        norms = np.linalg.norm(emb,axis=1,keepdims=True)
        if (norms == 0).any():
            raise ValueError("Zero blocker embedding")
        pairs = candidates(texts, emb / norms, cfg.blocker_threshold, cfg.blocker_top_k)
    else:
        pairs = []
    scores = score([(texts[a], texts[b]) for a,b,_ in pairs]) if pairs else []
    if len(scores) != len(pairs):
        raise ValueError("Matcher omitted candidate scores")
    relations, labels = [], {}
    for (a,b,s), (ab,ba) in zip(pairs,scores):
        kind = relation(ab,ba,cfg.entailment_threshold)
        labels[a,b] = kind
        relations.append({"a": a, "b": b, "blocking_score": s, "ab_margin": ab,
                          "ba_margin": ba, "relation": kind, "decision_stage": "nli"})
    groups = complete_link_groups(len(texts), labels)
    text_to_fact, facts = {}, []
    for g in groups:
        fid = "f_" + digest([texts[i] for i in g])[:24]
        facts.append({"id": fid, "canonical_text": texts[g[0]], "text_indices": g})
        text_to_fact.update({texts[i]: fid for i in g})
    return {"texts": texts, "facts": facts, "relations": relations,
            "mention_to_fact": {m["id"]: text_to_fact[m["text"]] for m in mentions},
            "pair_universe": len(texts)*(len(texts)-1)//2,
            "blocker_rejected_count": len(texts)*(len(texts)-1)//2-len(pairs),
            "implicit_relation": {"for": "unlisted distinct-text pairs within this case",
                                  "relation": "UNRELATED", "decision_stage": "blocker"},
            "cluster_policy": "complete_link"}


def match(cfg, run_dir):
    out = Path(run_dir)
    manifest = verify_run(cfg,out)
    index = json.loads((out / "extraction" / "index.json").read_text())
    if index["status"] != "complete" or index["config_hash"] != manifest["config_hash"]:
        raise ValueError("Matching needs a complete extraction from this configuration")
    by_case = {}
    for record in index["records"]:
        path = out / "extraction" / record["file"]
        if file_hash(path) != record["hash"]:
            raise ValueError("Extraction artifact changed")
        for m in json.loads(path.read_text())["mentions"]:
            by_case.setdefault(m["provenance"]["case_id"], []).append(m)
    target = out / "matching"
    target.mkdir(exist_ok=False)
    status = {"status": "running", "config_hash": manifest["config_hash"],
              "extraction_index_hash": file_hash(out / "extraction" / "index.json"),
              "environment": environment(), "cases": []}
    atomic_json(target / "index.json",status)
    try:
        from sentence_transformers import SentenceTransformer
        s = cfg.matching
        # Blocker stays on CPU so its weights do not compete with the 14B judge.
        blocker = SentenceTransformer(s.blocker_model, revision=s.blocker_revision,
            device="cpu", local_files_only=s.local_files_only)
        def encode(texts):
            if any(len(blocker.tokenizer.encode(t)) > blocker.max_seq_length for t in texts):
                raise ValueError("Atomic text exceeds blocker context; do not silently truncate")
            return blocker.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        model = LocalQwen(s)
        status["blocker_resolved_revision"] = getattr(blocker[0].auto_model.config,"_commit_hash",None)
        for cid, mentions in sorted(by_case.items()):
            result = match_mentions(mentions,s,encode,model.score)
            name = digest(cid)[:24]+".json"
            atomic_json(target/name, {"case_id":cid, **result})
            status["cases"].append({"case_id":cid,"file":name,"hash":file_hash(target/name)})
            atomic_json(target/"index.json",status)
        status.update(status="complete",model=model.metadata)
    except Exception as exc:
        status.update(status="failed",error_type=type(exc).__name__)
        raise
    finally:
        atomic_json(target/"index.json",status)
    return target
