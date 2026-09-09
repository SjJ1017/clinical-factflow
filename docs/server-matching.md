# Server-side pair annotation

The server labels every unordered pair of distinct atomic statements **within each case**. All five experimental conditions share the same case-level node inventory and annotation setting. It never compares unrelated patients. Exact text plus the same qualifier set share one node; all original mentions, annotations, quotations, spans, agent/round identifiers and run bindings remain attached. Different qualifiers remain different nodes. An identical-node comparison is identity, so it is not sent to the model.

The blocker is the first annotation stage. Its negative decisions and the local model's negative decisions have the same `relation: UNRELATED`. `decision_stage` records who made the decision. A model failure has a null relation and `pending` status; it is never an implicit negative.

## Transfer and run

Git transfers code, configuration and synthetic tests. Real extracted atoms, traces, credentials and weights are deliberately ignored. Transfer the atoms archive separately; the server does not need this laptop's directory structure, original repository, `.env`, raw traces or a cloud API key.

On the extraction machine, after the queue completes:

```bash
python -m clinical_factflow.server_matching bundle \
  --extraction runs/medcase24-m3-extraction-20260909 \
  --out exports/medcase24-atoms
```

This writes `exports/medcase24-atoms/` and `exports/medcase24-atoms.tar.gz`. Every source result and case file is hashed. Partial extraction is refused unless `--allow-partial` is explicitly supplied for a diagnostic snapshot; completeness remains attached to outputs. Transfer the archive to the server using your usual file-transfer method.

On a Linux server with Python 3.11+ and a CUDA-compatible PyTorch installation:

```bash
git clone https://github.com/SjJ1017/clinical-factflow.git
cd clinical-factflow
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[local,dev]'
python scripts/check_local.py
python -m pytest tests/ -q
```

The default is Qwen3-14B in BF16 on CUDA, with BGE on CPU. Model weights need a one-time public download (or a pre-populated Hugging Face cache). This command downloads the selected revisions and writes a pinned YAML; subsequent matching is local-only:

```bash
python scripts/prepare_matching_models.py \
  --config configs/matching/qwen14b.yaml \
  --out outputs/matching-resolved.yaml
mkdir -p exports
tar -xzf /path/to/medcase24-atoms.tar.gz -C exports
```

Run the entire blocker + local-model labeling + JSONL export with one command:

```bash
python scripts/server_match.py \
  --bundle exports/medcase24-atoms \
  --out outputs/medcase24-pairs \
  --config outputs/matching-resolved.yaml
```

Repeat that command to resume. Completed batches are skipped. An interrupted geometry build is archived and rebuilt; committed case ledgers are reused. Model failures stop the command with a nonzero exit status and keep completed observations. No replacement model or cloud fallback is used. After completion, rerunning makes no new judgments and creates a fresh export snapshot.

BF16 weights alone are about 28 GB in decimal units, before runtime memory. Batch size falls on CUDA OOM, down to one; effective batch sizes are recorded. Four-bit loading is an explicit new setting: install `.[quantized]` and use a separate YAML/output with `load_4bit: true`. Do not mix it into a BF16 ledger. Local GPU execution still needs validation on the destination server; the tests below validate the scoring interface, not GPU capacity or clinical accuracy.

## Saved values

Each case has a SQLite ledger, and the wrapper exports one JSONL file per case, including all blocker negatives. The row count is exactly `N * (N - 1) / 2`, where `N` is that case's distinct-node count.

| Stored field | Meaning |
|---|---|
| `cosine` | Cosine similarity of normalized BGE vectors |
| `lexical` | Shared token count / smaller token-set size |
| `token_intersection`, `a_token_count`, `b_token_count` | Components of the lexical score |
| `combined` | `max(cosine, lexical)` |
| `rank_a`, `rank_b` | Rank among all other nodes at each endpoint; deterministic index tie-break |
| `ab_margin`, `ba_margin` | Directional log YES-mass minus log NO-mass |
| `judgment.ab`, `judgment.ba` | Selected YES/NO token logits, full-vocabulary log normalizer, YES/NO log-probability masses, margin and conditional YES probability |
| `relation`, `decision_stage`, `reason`, `status` | Label, decision source, reason and completion status |
| `thresholds`, `policy`, `judgment_id` | Threshold setting and immutable observation reference |
| `test_data`, `input_complete` | Synthetic-score and incomplete-input markers |

The ledger also retains node-to-mention mappings, model/tokenizer revision and token IDs, full scoring configuration, input/code hashes, request attempts, and every past judgment/policy. Keep the SQLite files for the full history; a JSONL export is one policy snapshot. Back up ledgers after stopping the writer, or use SQLite's backup API, rather than copying a live database without its WAL.

Lexical tokenization is the existing lowercase alphanumeric/unit tokenizer with simple suffix stripping; its source hash is pinned. The blocker escalates a pair when `combined >= blocker_threshold` **and** it is in the top `K` of at least one endpoint. Everything else receives `UNRELATED`, with either `below_threshold` or `outside_both_top_k` as its reason.

The local model evaluates both `A ⇒ B` and `B ⇒ A` with thinking disabled. The four labels are `EQUIVALENT`, `A_ENTAILS_B`, `B_ENTAILS_A`, `UNRELATED`. The latter means neither directional entailment cleared the threshold; this is not a separate contradiction detector. The saved probability is conditional on the configured YES/NO token sets, not calibrated clinical confidence.

Defaults (`0.62`, top `12`, margin `5.28`) reproduce the inherited setting and are **not clinically calibrated**. Full-pair scores/ranks permit revisiting both blocker thresholds and top-K decisions. Counting distinct statements across the full case instead of separately within each run also defines the ranking pool; keep that pool frozen across conditions.

## Change thresholds without discarding observations

Changing only the NLI threshold uses saved model scores, with no forward passes:

```bash
python -m clinical_factflow.server_matching relabel \
  --results outputs/medcase24-pairs --policy initial \
  --name nli-5p0 --nli-threshold 5.0
```

Loosening the blocker can promote previously negative pairs. They become explicitly pending until scored; previously scored pairs reuse their observations:

```bash
python -m clinical_factflow.server_matching relabel \
  --results outputs/medcase24-pairs --policy initial \
  --name blocker-0p60-k20 --blocker-threshold 0.60 --top-k 20
python -m clinical_factflow.server_matching score \
  --results outputs/medcase24-pairs --policy blocker-0p60-k20 \
  --config outputs/matching-resolved.yaml
```

Original policies and scores stay intact. Reusing a policy name with identical settings resumes it; different settings require a new name. A new policy uses the latest stored observation for the same scoring setting; old policies continue pointing to their original judgments. Model, tokenizer, quantization, prompt, batch-setting or code changes require a separately versioned output, not an in-place continuation.

## Review boundaries

Export pairs near the blocker threshold, near the NLI margin threshold, or near the top-K boundary. Blocker negatives are included:

```bash
python -m clinical_factflow.server_matching review \
  --results outputs/medcase24-pairs --policy initial \
  --blocker-band 0.02 --nli-band 0.5 --out outputs/boundary-review
```

Inspect or narrow those JSONL files, then rerun selected pairs through the local model, including pairs initially labeled by the blocker:

```bash
python -m clinical_factflow.server_matching rejudge \
  --results outputs/medcase24-pairs --policy initial \
  --name boundary-second-pass --pairs outputs/boundary-review \
  --config outputs/matching-resolved.yaml
python -m clinical_factflow.server_matching export \
  --results outputs/medcase24-pairs --policy boundary-second-pass \
  --out outputs/boundary-second-pass-labels
```

Second-pass judgments append to history, leaving the original policy unchanged. Unselected pairs inherit exactly the specified parent policy; finish the parent before selective review. This is a new observation from the same model/configuration, not independent expert validation; deterministic local scores may be identical. For a different adjudicator or manual review, the exported pair IDs/texts and prior scores are the handoff material; preserve that as a separate measurement setting.

Validation results: [2026-09-09 execution report](server-matching-validation-20260909.md).

## Offline interface tests

```bash
# No weights, GPU, network or API key required.
python scripts/smoke_matching.py --out runs/random-interface-smoke

# Real BGE from a local cache; the model logits remain explicitly random.
python scripts/smoke_matching.py \
  --config configs/matching/bge-random-smoke.yaml \
  --out runs/bge-interface-smoke
```

Both use deterministic seeded random logits in the exact detailed-score contract used by Qwen. Synthetic outputs carry `test_data: true`. Each covers two synthetic cases, 48 nodes and 552 pairs, including interrupted/resumed batches, zero-call completed resume, threshold expansion, boundary review and full JSONL export. These labels are not semantic accuracy measurements.

The new server entry point supersedes the old per-run `match` command for this study's all-pair ledger. The legacy command remains available for historical smoke runs; it does not produce this ledger format.

## Measure the matching workload before GPU execution

The approved plan keeps `blocker_threshold: 0.62` and `top_k: 12`, with one GPU process. Use 7.25 complete bidirectional pairs per second for planning; do not divide the estimate by two again. The actual GPU throughput still depends on the destination hardware.

```bash
python scripts/profile_blocker.py \
  --bundle exports/medcase24-atoms \
  --out outputs/blocker-workload \
  --config outputs/matching-resolved.yaml \
  --pairs-per-second 7.25
```

This uses the production BGE/lexical geometry and makes no NLI calls. It retains every pair's scores, lexical components and endpoint ranks in compressed arrays, with embeddings, node identities and input/code/model hashes. Repeating the same profile reuses verified geometry. Changed input, encoder or geometry code requires a new output directory. The final summary compares threshold and top-K choices and reports unique shared-case candidates, the subset that occurs together within individual traces, and projected GPU hours. The shared-case total is the execution workload; per-trace counts can overlap and must not be substituted for it.

The profile cache is an offline planning artifact. Production matching writes its own complete SQLite annotation ledger; transfer the atoms archive and preserve the production ledgers for threshold changes and second judgments.

## Prepared Chewie launcher

After the prepared server's physical GPU 4 is fully idle:

```bash
cd ~/clinical-factflow && GPU=4 ./scripts/run_server_matching.sh
```

Set `GPU` to the available physical index from `nvidia-smi`. GPU 3 is too small. The launcher refuses cards with an existing compute process, nonzero utilization, more than 256 MiB already used or less than 38,000 MiB total memory. It does not wait or pick a different card. It resolves the UUID before tmux creation and verifies the binding again inside tmux. The actual CUDA kernel/UUID check is performed only at that future launch.

The prepared resolved configuration is `outputs/matching-chewie.yaml`; it uses the existing cached model snapshots. The default interpreter is `/scratch/users/jiajun/venv-matcher/bin/python`; project imports come from this checkout. Output and the append-only launcher log are under `/scratch/users/jiajun/clinical-factflow/medcase24-pairs`. Cache and temporary paths follow the original `fact-agent/experiments/matcher_eval/run.sh` layout. Existing environments, jobs and tmux sessions are left untouched.

Attach with `tmux attach -t clinical-matching`. A successful or failed run leaves its log and matching checkpoints on disk; repeat the launch command to resume once its tmux session has ended. An existing same-name session is never replaced. `MATCH_SESSION`, `MATCH_OUT`, `MATCH_CONFIG`, `MATCH_BUNDLE` and `PYTHON` can explicitly override paths or session name.


## Parallel case shards

`python scripts/split_matching_bundle.py --bundle exports/medcase24-atoms --profile outputs/blocker-workload-full.json --out exports/medcase24-two-gpu --names gpu0 gpu4` partitions whole cases by measured default candidate counts. It validates the full manifest and every case hash, records a disjoint exhaustive assignment in `plan.json`, and copies original case files unchanged. Every case retains its complete original ranking pool. Parent extraction record counts remain explicitly marked as parent provenance in each shard.

Launch separate tmux sessions/output directories with `GPU=0 MATCH_SESSION=clinical-match-gpu0 MATCH_BUNDLE=exports/medcase24-two-gpu/gpu0 MATCH_OUT=/scratch/users/jiajun/clinical-factflow/medcase24-pairs-gpu0 ./scripts/run_server_matching.sh`, and the analogous GPU 4 settings. Both output sets and the split plan together form the study; completion of one shard is not completion of the full study. Repeating an individual launch resumes that shard without changing its frozen case inventory.
