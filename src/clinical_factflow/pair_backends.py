"""Identical detailed-score contracts for a local Qwen model and random test data."""

from __future__ import annotations
import hashlib, inspect, math
import numpy as np
from .matching import LocalQwen


def stable_seed(seed, *parts):
    return int.from_bytes(
        hashlib.sha256(repr((seed, parts)).encode()).digest()[:8], "big"
    )


def random_direction(seed, pair_id, direction, round_id):
    rng = np.random.default_rng(stable_seed(seed, pair_id, direction, round_id))
    # Deliberately cover all relation outcomes around the inherited margin cutoff.
    yes = float(rng.normal(3, 5))
    no = float(rng.normal(0, 3))
    other = float(rng.normal(4, 2))
    z = float(np.logaddexp(np.logaddexp(yes, no), other))
    return {
        "yes_token_logits": {"1": yes},
        "no_token_logits": {"2": no},
        "log_normalizer": z,
        "yes_logprob_mass": yes - z,
        "no_logprob_mass": no - z,
        "margin": yes - no,
        "conditional_yes_probability": float(1 / (1 + math.exp(-(yes - no)))),
    }


class RandomLogitScorer:
    def __init__(self, seed=42):
        self.seed = seed
        self.metadata = {
            "backend": "random_mock",
            "test_data": True,
            "seed": seed,
            "yes_no_token_ids": {"YES": [1], "NO": [2]},
        }

    def score(self, pairs, round_id="initial"):
        return [
            {
                "pair_id": p["pair_id"],
                "ab": random_direction(self.seed, p["pair_id"], "ab", round_id),
                "ba": random_direction(self.seed, p["pair_id"], "ba", round_id),
            }
            for p in pairs
        ]


class QwenLogitScorer(LocalQwen):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.metadata.update(
            backend="local_qwen",
            test_data=False,
            enable_thinking=False,
            tokenizer_resolved_revision=self.tok.init_kwargs.get("_commit_hash"),
        )

    def detailed(self, pairs):
        import torch

        cfg = self.cfg
        prompts = [
            self.tok.apply_chat_template(
                [
                    {"role": "system", "content": cfg.system_prompt},
                    {"role": "user", "content": cfg.user_template.format(a=a, b=b)},
                ],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            for a, b in pairs
        ]
        result = []
        i = 0
        batch = cfg.batch_size
        keep = (
            {"logits_to_keep": 1}
            if "logits_to_keep" in inspect.signature(self.net.forward).parameters
            else {}
        )
        self.metadata["last_token_only_forward"] = bool(keep)
        while i < len(prompts):
            enc = self.tok(
                prompts[i : i + batch],
                return_tensors="pt",
                padding=True,
                add_special_tokens=False,
                truncation=False,
            ).to(self.net.device)
            if enc["input_ids"].shape[-1] > self.net.config.max_position_embeddings:
                raise ValueError("Logic prompt exceeds context: never truncate a fact")
            try:
                with torch.inference_mode():
                    logits = self.net(**enc, **keep).logits[:, -1, :].float()
                z = torch.logsumexp(logits, dim=-1)
                y = torch.logsumexp(logits[:, self.ids["YES"]], dim=-1) - z
                n = torch.logsumexp(logits[:, self.ids["NO"]], dim=-1) - z
                batch_result = []
                for row in range(len(y)):
                    margin = float((y[row] - n[row]).item())
                    detail = {
                        "yes_token_logits": {
                            str(k): float(logits[row, k].item())
                            for k in self.ids["YES"]
                        },
                        "no_token_logits": {
                            str(k): float(logits[row, k].item()) for k in self.ids["NO"]
                        },
                        "log_normalizer": float(z[row].item()),
                        "yes_logprob_mass": float(y[row].item()),
                        "no_logprob_mass": float(n[row].item()),
                        "margin": margin,
                        "conditional_yes_probability": float(
                            torch.sigmoid(y[row] - n[row]).item()
                        ),
                    }
                    batch_result.append(detail)
                result.extend(batch_result)
                self.metadata["effective_batch_sizes"].append(len(y))
                i += len(y)
                del logits, enc, z, y, n
            except torch.OutOfMemoryError:
                if "logits" in locals():
                    del logits
                if "z" in locals():
                    del z
                if "y" in locals():
                    del y
                if "n" in locals():
                    del n
                del enc
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                if batch == 1:
                    raise
                batch = max(1, batch // 2)
        return result

    def score(self, pairs, round_id="initial"):
        ab = self.detailed([(p["a_text"], p["b_text"]) for p in pairs])
        ba = self.detailed([(p["b_text"], p["a_text"]) for p in pairs])
        return [
            {"pair_id": p["pair_id"], "ab": a, "ba": b}
            for p, a, b in zip(pairs, ab, ba)
        ]


class RandomEncoder:
    def __init__(self, seed=42, dimensions=24):
        self.seed, self.dimensions = seed, dimensions
        self.metadata = {
            "backend": "random_mock",
            "test_data": True,
            "seed": seed,
            "dimensions": dimensions,
        }

    def encode(self, texts):
        return np.array(
            [
                np.random.default_rng(stable_seed(self.seed, t)).normal(
                    size=self.dimensions
                )
                for t in texts
            ]
        )


class BGEEncoder:
    def __init__(self, cfg):
        from sentence_transformers import SentenceTransformer

        self.net = SentenceTransformer(
            cfg["model"],
            revision=cfg["revision"],
            device=cfg.get("device", "cpu"),
            local_files_only=cfg["local_files_only"],
        )
        self.metadata = {
            "backend": "sentence_transformer",
            "test_data": False,
            **cfg,
            "resolved_revision": getattr(
                self.net[0].auto_model.config, "_commit_hash", None
            ),
            "max_seq_length": self.net.max_seq_length,
        }

    def encode(self, texts):
        if any(
            len(self.net.tokenizer.encode(t)) > self.net.max_seq_length for t in texts
        ):
            raise ValueError("Atom exceeds blocker context: never silently truncate")
        return self.net.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
