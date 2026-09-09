# Clinical Factflow

A new, independent project for controlled multi-agent experiments and atomic fact tracing. The runner accepts domain-neutral evidence records; the supplied extraction taxonomy and dataset adapters focus on clinical cases.

**Dataset decision and access review:** [research memo](docs/dataset-feasibility.md). **Experimental rationale:** [design](docs/research-design.md). **Lessons carried over:** [pitfall audit](docs/pitfall-audit.md).

Only the pipeline lives here: run generation, local dataset adapters, extraction with occurrence annotations, a second atomization pass, and local directional NLI. No previous traces, extracted facts, labels, reports, analysis scripts, credentials, caches, or Git history were imported. `examples/` contains one newly authored engineering fixture, not clinical research data.

## Install and verify without network calls

Use Python 3.11+ (3.11/3.12 recommended on the GPU host):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/clinical-factflow validate configs/demo-full.yaml --with-data
.venv/bin/clinical-factflow compare configs/demo-full.yaml configs/demo-star.yaml
.venv/bin/clinical-factflow compare configs/demo-full.yaml configs/demo-chain.yaml
```

`validate` does not call an LLM or load model weights. Without `--with-data` it also works before restricted datasets have been obtained. `compare` fails on any changed field outside its explicit allowlist; changing an agent prompt cannot silently pass as a topology-only comparison. `schema --out run.schema.json` exports the configuration schema.

## One complete YAML per run

Every supplied YAML contains the exact task/role/extraction/atomization/NLI prompts, model settings, rounds, schedule, topology order and edges, information allocation, initial contexts, source visibility, self/peer memory, cohort selection, replicate, outcome rule and matching parameters. There is no base-file inheritance, CLI model override, or topology-specific prompt selection.

| File | Purpose |
|---|---|
| `demo-full.yaml`, `demo-star.yaml`, `demo-chain.yaml` | Same agents, prompts, source distribution and synchronous schedule; only topology changes |
| `demo-chain-sequential.yaml` | Explicitly different schedule: each successor sees its predecessor in the same round |
| `demo-shared.yaml` | Same panel with all source evidence available to every agent |
| `demo-generalists.yaml` | Same split and topology, identical general-clinician prompts, separate generation calls |
| `demo-solo.yaml` | One general clinician, all evidence, one call; information-sufficiency baseline, not a compute-matched comparison |
| `clinicalbench-pilot.yaml` | Approved local source path; remote processing disabled pending permission review |
| `medcasereasoning-pilot.yaml` | Local official Parquet/JSONL; case presentation only, all reference fields withheld |
| `ddxplus-pilot.yaml` | Local CSV plus evidence dictionary; mechanism control, not a multidisciplinary clinical main benchmark |

The `demo-*` files use the synthetic fixture. Point them at an audited cohort before research. The three real-dataset files use `limit: 1` as smoke configurations, not defensible experiment sizes. Pin the cohort using `case_ids`, and use a new complete YAML for each replicate. Relative data paths resolve against the YAML's directory.

`by_category` assigns entire reports using category names. `explicit` assigns source IDs; `round_robin` is a mechanical control; `shared` exposes all evidence. Missing assignments fail before calls. Roles and information allocation are separate configuration fields: changing a role never changes its evidence automatically.

## Execute stages

Export credentials explicitly in your shell. `.env.example` contains names only; the package does not search parent folders for `.env` files or provider fallbacks.

```sh
# Calls the configured generation endpoint; inspect YAML before running.
.venv/bin/clinical-factflow run configs/demo-full.yaml --out runs
# Use the exact RUN_DIR printed by the preceding command:
.venv/bin/clinical-factflow extract configs/demo-full.yaml --run-dir runs/RUN_DIR
# On a host with local Qwen/BGE weights and the local extra installed:
.venv/bin/clinical-factflow match configs/demo-full.yaml --run-dir runs/RUN_DIR
```

`pipeline CONFIG --out runs` runs all three stages. Defaults are generation `deepseek-v4-flash` and extraction/atomization `minimax-m2.5`, using **OpenCode Go** (`/zen/go/v1`), with no automatic fallback to a metered endpoint. Local chat-compatible endpoints can replace either stage in the YAML. Restricted cases and their derived text must not be sent remotely merely because an API key exists: `dataset.allow_remote_processing: false` blocks both hosted generation and extraction.

Every `run` creates a distinct directory, including when identical YAML is repeated. There is no generation response cache, so identical generalist prompts still cause independent calls. Provider seed support is not guaranteed; when a seed is configured, per-case/agent/round/replicate seeds differ and are recorded in requests. Replicates remain necessary.

To continue on a GPU machine, transfer the same code, YAML and permitted private run artifacts. Relative source paths are resolved locally without changing the configuration fingerprint; matching uses the frozen extraction rather than reopening the dataset. Do not change matching settings after generation: choose the intended host/model settings in the original run YAML. A changed measurement protocol belongs to a new run.

## Local matching

```sh
.venv/bin/python -m pip install -e '.[local]'
# Populate your existing HF cache explicitly if weights are not already present.
# These downloads are large; the matcher itself defaults to local_files_only=true.
CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 \
  .venv/bin/clinical-factflow match configs/demo-full.yaml --run-dir runs/RUN_DIR
```

Default checkpoint: **Qwen/Qwen3-14B**, bf16, eager attention, batch 16. It asks the original YES/NO entailment question in both directions, disables Qwen thinking in the chat template, and computes first-token `log P(YES) − log P(NO)`. The **5.28** threshold is inherited from the old science-domain calibration, **not a validated clinical cutoff**. The YAML records that limitation. Use an independently annotated clinical development/test split before reporting matcher accuracy; this scaffold does not claim to have calibrated the model.

The blocker is **BAAI/bge-base-en-v1.5**, threshold **0.62**, top-k **12**, using `max(cosine, token containment)` as the existing code does. It operates on distinct texts within each patient, preserving every mention. Rejected pairs are UNRELATED by pipeline definition, represented compactly with a count and an implicit decision rule. Adjudicated pairs retain both margins and the decision stage. Two NO directions are also UNRELATED in this pipeline; this does **not** separately identify contradiction.

Only bidirectional entailment forms equivalence. Complete-link grouping requires a directly scored equivalence for every pair in a cluster, preventing union-find transitivity from manufacturing equivalence. This is a deliberate new measurement protocol; old fact IDs or old absolute rates must not be mixed with its results. Direct relations remain available even if conservative clustering separates a pair. Cluster IDs are scoped to one case/run; they are not a cross-run semantic identity service.

Use `scripts/check_local.py` to inspect the actual visible GPU and installed runtime before loading 14B. Set `HF_HOME` to your own existing cache location when appropriate. The matcher never hardcodes an old server's scratch path or GPU number. Four-bit loading is optional in YAML and requires the `quantized` extra; it changes the measurement setting and needs separate validation. Requested model revisions, resolved commits when available, token IDs, effective batches and package versions are stored. Replace `revision: main` with a commit SHA for release experiments.

## Records and annotations

```text
runs/RUN_DIR/
  manifest.json               # full config, hashes, cohort, edges, allocation, environment
  cases.json                  # evidence snapshot; no reference answer field
  references.private.json     # evaluation references, never fed to agents/extractor
  trace.json                  # original output, exact messages, actual visible IDs, outcome
  calls/generation/*.json     # every HTTP attempt, usage, raw response, latency
  calls/extraction/*.json     # includes retries and atomization
  extraction/index.json       # completeness and checksums
  extraction/*.json           # parents, final mentions, annotation, all quoted spans
  matching/index.json         # completeness, settings and local runtime identity
  matching/*.json             # per-case facts, directional relations and mention mapping
```

These artifacts can contain dataset content; the entire `runs/` tree is private and ignored by Git. Request headers and API keys are never saved. A configuration hash includes prompts and schema-bearing source code is also hashed. Later stages reject changed configuration, changed code, incomplete upstream stages and altered input artifacts. Interrupted stages are explicitly failed/incomplete; they are not mixed into a complete corpus. Automatic resume and cross-run caches are intentionally absent in this small version.

The raw JSON response is retained. In the revised diagnostic protocol, `final_diagnosis` is appended as a separate final line and selected explicitly for voting with `outcome.answer_field`; explanations remain in `assessment`/`answer`. Every round has its own outcome record. For legacy outputs, the agent's `assessment` and `answer` strings are rendered as `assessment + "\nFinal answer: " + answer`; span offsets refer to that rendered output, not to the raw JSON envelope. Provider token usage refers to the actual API call, and is kept separately.

Annotations are per **mention**, not per cluster: `kind`, `attribution`, `certainty`, `polarity`, `clinical_domain`, `attributed_to`. Thus an observation can also be reported; "relay" is not forced into an exclusive choice with "fact". Semantic transmission still needs the actual visibility record plus matching, not the speaker's attribution alone. The extractor has no gold answer, and these labels are not expert truth labels. See [annotation conventions](docs/annotations.md).

Accuracy: `outcome.scoring: exact` requires explicit accepted answers and is appropriate for closed labels such as DDxPlus. Free-text clinical tasks default to **ungraded**, with predictions and references retained for a future verified evaluator. String comparison is not passed off as ClinicalBench's original metrics. A majority tie abstains. Reliability is recorded separately from outcomes; token usage (including reasoning details if supplied) and latency are preserved per attempt, not guessed from character counts. Monetary rates are not hardcoded.

## Current boundaries

The new prompts incorporate known extraction failures and are a **new protocol**. Offline tests verify plumbing and failure handling; they do not establish clinical extraction/NLI accuracy. No live generation, minimax extraction, 14B model inference, full dataset download or data-access submission was performed when building this project. Local-model inference still needs verification on the intended GPU host.

The direct ClinicalBench adapter handles documented report fields but requires a real-cohort audit of summary boundaries, omitted sections, time cutoffs and diagnosis leakage. It does not silently fix invalid JSON. MedCaseReasoning is kept as an intact presentation; a clinician-reviewed, lossless partition should be exported in the canonical format for role × information studies, rather than assigning guessed specialties by keyword. MIMIC-CDM and nonmedical candidates are evaluated in the research memo; they are **not claimed as integrated adapters**. A generic canonical adapter lets reviewed evidence partitions enter the same runner.

## Frozen MedCaseReasoning pilot: 24 cases × 5 conditions

See [selection, partition caveats and experiment design](docs/medcase24-pilot.md).
`configs/pilots/medcase24/` contains 120 complete run YAMLs for the shared/split ×
generic/specialist design plus fully mismatched specialists. The preparation and
integrity-checking scripts live in `scripts/medcase24/`; they make no model calls.

The selected source text, reference answers, generated viewer and screening audit
are local files under the ignored `data/medcasereasoning/pilot24/` directory. They
are not included in this Git repository. Rebuild them from the pinned official
training Parquet using the instructions in the selection memo before validating or
running the pilot configs. The partitions were reviewed by an assistant, not
clinician-certified. All 120 main-study traces are now complete; see the
[generation report](docs/medcase24-generation-20260909.md). The separate
LLM-assisted, level-aware correctness evaluation remains pending.

## Model and credential preference

The current defaults are DeepSeek V4 Flash for agent reasoning, MiniMax M2.5 for
extraction/atomization, and local Qwen3-14B for matching. Non-historical YAMLs name
`OPENCODE_API_KEY_2` explicitly. Missing API 2 does not trigger fallback to API 1.
The 2026-09-09 smoke YAMLs record the actual earlier API 1 / DeepSeek validation
settings and are retained unchanged. See [smoke findings](docs/deepseek-smoke-20260909.md).

OpenCode Go requires the client's own user agent and a stable conversation session
header; the client now provides both and preserves separate agent conversations.
[Provider requirements](https://opencode.ai/docs/go/#where-can-i-use-it).

## Revised same-patient diagnosis validation

[Protocol, per-round accuracy, measured Go usage and 120-trace forecast](docs/revised-smoke-20260909.md).
The user approved the 120-case-condition generation study on 2026-09-09, with
later [LLM-assisted, level-aware evaluation](docs/diagnosis-evaluation.md). Shared
patient metadata is limited to an opaque study ID, age and sex as reported. Every
revised diagnostic turn ends in a dedicated `final_diagnosis`; majority voting uses
that field rather than the explanation. Disease-only formatting does not guarantee
semantic agreement on synonyms or syndrome versus etiology.

The independent checkout has its own ignored `.env` containing the OpenCode keys.
Export its values explicitly before a live command; the client does not search the
old project and never silently falls back from API 2:

```sh
set -a
source .env
set +a
```

## MedCase24: generation completed

[All 120 traces, integrity checks and actual resources](docs/medcase24-generation-20260909.md).
All 1,080 diagnostic outputs are saved locally. LLM-assisted precise/level-correct/incorrect
evaluation is a separate pending stage; literal majority is not the primary accuracy
metric. The generation run has not executed extraction, atomization or matching.


MiniMax extraction quality pilot: [2026-09-09 audit](docs/minimax-extraction-pilot-20260909.md).
Ten texts completed (162 final mentions), but input-only imports and domain omissions
make the current output extraction unsuitable for a full measurement corpus without
further validation. The versioned pilot keeps the atom fields and makes domains multi-select.
