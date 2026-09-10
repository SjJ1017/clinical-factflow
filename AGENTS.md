# Working rules

This repository has no dependency on the old fact-agent checkout. Read README.md,
docs/pitfall-audit.md and docs/dataset-feasibility.md before changing the pipeline.

- One complete YAML per run. No topology-specific prompt branches or hidden overrides.
- Keep roles, source allocation, scheduling and memory as independent variables.
- Do not silently reuse generation responses across agents, rounds or replicates.
- Default hosted endpoints are OpenCode Go. Do not introduce metered fallbacks.
- Do not run live experiments merely to check code; use the offline tests first.
- ClinicalBench is application-only and has restrictive data terms. MIMIC data also
  has access and processing restrictions. A local file or a working API key is not
  evidence that cloud processing or publication is authorized.
- Gold stays in the evaluator reference file. Never add it to generation, extraction,
  input allocation or case selection prompts.
- Never treat an absent reference fact as false; gold rationales may be incomplete.
- Failed calls/stages and unlocated spans stay explicit. Do not silently repair data,
  fill empty extractions, default missing relation scores to UNRELATED, or publish partial runs.
- Blocker-rejected pairs ARE UNRELATED by the configured pipeline, with decision-stage
  provenance. This is different from missing/failed NLI scores.
- Do not loosen semantic matching to conceal extraction granularity problems.
- All local model, tokenizer, quantization and threshold changes define a new measurement setting.
- No data, generated outputs, credentials or model weights in Git. Use synthetic fixtures in tests.

## User-confirmed defaults (2026-09-09)

- Agent diagnosis/reasoning: `deepseek-v4-flash` through OpenCode Go.
- Extraction and second atomization pass: `minimax-m2.5`, the established default;
  do not switch to DeepSeek merely because agent inference uses DeepSeek.
- Semantic matching: default local `Qwen/Qwen3-14B` with BGE blocking.
- Prefer `OPENCODE_API_KEY_2`. Keep the key choice explicit in every YAML; if it is
  unavailable, report the missing variable rather than silently consuming API 1.
- The 2026-09-09 DeepSeek extraction smoke samples are a user-accepted validation
  exception, not the production measurement protocol. Their grounding audit failed:
  one output extraction imported input-only facts and quotes were not always exact.
- State explicitly that all evidence partitions and peer reports concern the same
  patient in a future protocol; some smoke agents wrongly treated peers as a
  different patient. Do not rewrite completed traces to conceal this behavior.

## Revised smoke and approval gate (2026-09-09)

- Read `docs/revised-smoke-20260909.md` before the 24 × 5 study. Two revised
  split-specialist traces are complete. On 2026-09-09 the user approved execution
  of all 120 main-study traces conditional on later level-aware, LLM-assisted
  evaluation. That condition is documented in `docs/diagnosis-evaluation.md`.
  Generation is now authorized; extraction/matching/judging are separate stages.
- New runs share only an opaque patient ID, age and reported sex, and explicitly
  state that peer reports concern the same patient. These common fields are
  deliberate duplicates, not three independent sources of evidence.
- Revised diagnosis voting uses the required `final_diagnosis` field. Keep raw
  `answer`/assessment for audit. One disease name does not resolve label ontology:
  tumor-induced osteomalacia and its causative PMT are not interchangeable labels.
- This checkout's `.env` is independent and ignored (mode 0600). Read API 2 here;
  never depend on the old checkout for credentials or commit real key values.
- The user explicitly deferred extraction/atomization fixes. Do not silently
  bundle them into this diagnostic protocol change or spend API calls on them.

## User-approved evaluation (2026-09-09)

- Use precise_correct / level_correct / incorrect after reference-aware clinical
  comparison, with explicit unresolved review flags. Exact strings alone are not
  the primary metric. Read `docs/diagnosis-evaluation.md`.
- Semantic system aggregation must be reference-blind. Never resolve a vote using
  gold labels or count individually correct agents as the system prediction.

## Completed MedCase24 generation (2026-09-09)

- All 120 fresh main-study traces are complete in `runs/medcase24-approved-20260909/`.
  Check `status.json` and `audit.json` before running anything. Do not regenerate them.
- Read `docs/medcase24-generation-20260909.md` for actual resources, retry accounting
  and the separate pending three-label judging stage. No judged accuracy exists yet.
- R1–R3 are reusable for a future explicit R4+ continuation, but no continuation
  entry point exists yet. Do not edit original YAMLs or silently rewrite parent runs.


## MiniMax extraction audit (2026-09-09)

- User authorized only a small MiniMax extraction/atomization quality check and
  explicitly rejected additional atom attributes. It is complete: see
  `docs/minimax-extraction-pilot-20260909.md` and the existing ignored
  `runs/minimax-extraction-pilot-20260909/` before any new API work.
- Keep atom fields unchanged; `clinical_domain` is now a nonempty multi-label list
  of the existing vocabulary. Old string-domain artifacts are a different version.
- MiniMax M2.5 on Go uses `api_format: anthropic` (`/messages`); DeepSeek generation
  remains OpenAI-compatible. Native Anthropic cache counters are separate from input.
- The pilot failed grounding readiness: 20 input-only imports in one R3 sample;
  137/162 mentions had exact target quotes; 24 clear domain problems, 12 boundaries.
  Short direct sources looked better; do not infer a model-wide quality rate or role effect.
- Both extraction and atomization can import context-only facts. Do not solve this by
  labeling imported facts as false, deleting them silently, or loosening matching.
- Do not rewrite the completed 120 generation configs/artifacts or regenerate them
  to adopt the new extraction schema. This pilot has its own parent-linked hashes.
- All calls including an 8,000-token truncation are accounted: 10.74 min, estimated
  $0.07663 Go allowance. Twelve responses omit cache fields; no cash-bill reconciliation.
- No full extraction, matching, or paid diagnosis judging was authorized by this audit request.


## Output-only extraction and thinking follow-up (2026-09-09)

- User confirmed the boundary: extract each output from that output alone. Do not
  expose full agent input as reference context in either pass. Reuse previously
  extracted delivered facts for input profiles; original evidence/common metadata
  need initial extraction and should be reused too. A cross-run cache is not yet implemented.
- Read `docs/minimax-context-and-thinking-20260909.md`. The 20 context-only final
  facts were all traceable to first-pass text OR qualifiers; atomization promoted
  one qualifier. Do not repeat the earlier claim of an independent new import.
- 51,207 was total output tokens, not thinking tokens. All 23 calls had thinking;
  136,016 thinking characters and 94,799 formal characters, without a token split.
- MiniMax M2.x provider docs say thinking cannot be disabled. Do not claim
  `thinking: disabled` solves cost. No new model or hard reasoning budget is set.
- Output-only v2 is implemented and offline-tested, not yet live-validated.
  Preserve old pilot config and traces as v1 evidence; no paid calls this follow-up.


## Token-ratio correction and throughput comparison

- API reasoning usage is absent, but the official M2.5 tokenizer now provides an
  offline estimate: thinking 27,776 vs formal 23,339 (54.3%/45.7%); successful
  attempts alone are 46.4% thinking. Sum differs from API by four tokens per call.
  See `docs/minimax-context-and-thinking-20260909.md`, private `tokenizer-audit/`.
- Do not equate 51,207 total output tokens with reasoning or repeat that no token
  split can be estimated at all. Distinguish offline tokenizer counts from billing.
- Old retrace defaults to concurrency 6, candidate-only atomization, compact
  ID/string replies and run-level batches; the new pilot was serial, all-parent,
  per-record, full annotated replies. Thinking is only part of the throughput gap.
- User rejects a tens-of-hours execution plan and recalls about one hour before.
  Audit/optimize these differences before a new full-run schedule. The exact old
  one-hour workload is unverified; do not promise matching runtime without a pilot.


## Candidate-only speed retest (2026-09-09; supersedes historical all-parent advice)

- User requested output-only input, screened-parent atomization and a ten-text six-worker retest. Completed; read `docs/minimax-candidate-speed-20260909.md` before more calls.
- M2.5 v3: 10/10, 177.93 s batch wall, 40/128 parents reviewed, 165 mentions, 159 located. Returned thinking/formal tokens: 21,610/17,400; timeout usage unknown. Aggregate call work did not improve; do not attribute parallel speedup to prompts.
- Known context-only imports disappeared in manual review; compounds, scope errors, duplicates and domain omissions remain. Location rate is not semantic accuracy or recall.
- Default reusable presets: `atomize: candidates_v1`, six workers. Unselected parents retain all fields. Selection reasons are stage metadata. Do not add atom attributes.
- M3 speed pilot: only S03/S04, thinking explicitly disabled, 20.56 s concurrent wall, four successful calls, 61/61 located. Joint-condition splitting and duplicate evidence remain; M2.5 stays the default. Do not claim clinical quality validation.
- Reuse-aware M2.5 full extraction projects 6.1–6.8 ideal hours at six workers; current naive per-run calls duplicate sources/metadata (7.74 h per-record projection). Cross-run reuse still needs implementation. No full extraction/matching/judging was launched.


## M3 chosen and ten-text accuracy review (2026-09-09)

- User chose M3 with thinking disabled. Future reusable root configs now use `minimax-m3` with `extra_body.thinking.type: disabled` for extraction/atomization, API 2, candidate-only, six workers. This supersedes the earlier M2.5 default. DeepSeek generation and frozen runs are unchanged.
- All ten original sample texts have M3 results: reuse S03/S04 from the speed pilot, eight new results in `runs/minimax-m3-accuracy-completion-20260909/`. Do not redo them. Full private review is `runs/minimax-m3-accuracy-review-20260909/`; public summary `docs/minimax-m3-accuracy-20260909.md`.
- 194 mentions, 194 located; strict fidelity pass 174 (10 clear errors, 10 review), domain-set pass 163 (24 clear errors, 7 review). This is unblinded Codex review, not clinician gold, clinical diagnosis accuracy or recall. Duplicate/granularity differences affect denominators.
- 18/18 calls successful, zero returned thinking blocks, $0.03616 known allowance. New eight ran in 21.26 s; earlier two in 20.56 s. Do not claim a simultaneous ten-text benchmark. Reuse-aware six-worker full extrapolation 1.14–1.24 h, planning 1.5–2 h, plus matching/judging.
- Joint-condition errors, missing shared durations, duplicate expansions and domain omissions persist. No new atom attributes or prompt fixes were introduced. No full extraction/matching/judging was launched by this accuracy check.


## Authorized timed extraction (2026-09-09)

- User authorized production M3 extraction for about 30 minutes, stopping by 17:00 Europe/Zurich. Started at 16:32; hard deadline 15:00 UTC. Read `docs/resumable-extraction.md`.
- Active stage: `runs/medcase24-m3-extraction-20260909/`. Before starting any extraction, check its status, results and lock. Do not create a duplicate sweep. 1,487 tasks map to 3,355 original records with source/metadata reuse and output provenance isolation.
- Resume through `python -m clinical_factflow.resumable_extraction` using the same study/config/out and a fresh duration. Do not copy the expired September 9 `--stop-at` into future runs. Private `resume.sh` schedules another 30 minutes only when explicitly run.
- Both initial extraction and individual atomization batches have sealed checkpoints; successful raw responses can recover a narrowly interrupted checkpoint write. Completed records are hash-verified and skipped. Unknown in-flight usage remains unknown.
- No automatic continuation after the cutoff is authorized. Matching and diagnostic judging remain separate. Full extraction is now authorized, but this session's runtime is explicitly bounded.


## Timed extraction paused — final state (2026-09-09)

- Stopped cleanly at 16:59:58 Europe/Zurich, before 17:00. Process exited; queue lock free. Do not treat the earlier running updates as current.
- 616/1,487 records complete: 297 outputs, 300 unique sources, 19 metadata records. 25/120 trace extractions fully covered. 871 pending, including six validation-failed records; one pending record has a reusable successful stage checkpoint.
- 1,037 successful requests saved; all finished result/task/record hashes verified. Real 30-record offline resume test made zero additional calls. 61 offline tests include a hung-worker hard-deadline test.
- Known Go allowance $2.013; five deadline-related timeouts have unknown usage. No returned thinking blocks. Local session report and immutable first-session summary are in the queue directory.
- No automatic continuation. `runs/medcase24-m3-extraction-20260909/resume.sh` uses the frozen private config and runs another 30 minutes only when invoked. Preserve checkpoints and source version; do not start a duplicate extraction directory.


## Resume and portable matching (2026-09-09, latest user authorization)

- The user explicitly resumed all remaining production extraction. The 17:00 cutoff applied to the earlier completed session; do not mistake its 616-record summary for the latest state. Read the current queue status and lock before any new launch.
- `scripts/continue_extraction.py` uses the frozen extraction engine and schedules previous failures last. `scripts/recover_extraction_schema.py` is an explicit, separately audited schema-validation retry for failed stages only, with distinct request keys. It keeps the same M3 settings, target-only text, atom schema and successful checkpoints. Never hand-map invalid model annotation values or overwrite valid records.
- Server annotation uses `scripts/server_match.py` / `clinical_factflow.server_matching`, independent YAMLs in `configs/matching/`, and the atoms-only bundle. Read `docs/server-matching.md`. The legacy per-run matcher is not the all-pair export.
- Every same-case distinct-node pair has a row. Blocker and local-model negatives share UNRELATED; model failures remain null/pending. Store lexical components, cosine, endpoint ranks, both directional YES/NO logits/log masses and margins, settings and decision provenance. Never drop blocker negatives.
- Threshold policies append to the ledger; selected boundary rejudgments append observations. Missing scores after blocker expansion need actual scoring. Old labels and observations stay available. Real Qwen GPU accuracy/performance is not established by synthetic interface tests.
- Git excludes real data/ledgers. Transfer the generated atom archive separately. Mock outputs use test_data=true and cannot be cited as semantic results.


## Extraction paused by API 2 weekly quota — latest state

- Resumed queue stopped cleanly at 1,157/1,487 completed (541 new); 330 remain. API 2 returned HTTP 429 / GoUsageLimitError / weekly, with about four days until reset. A single probe confirmed it. Do not repeatedly retry this known quota failure or enable paid balance.
- All saved record/task hashes and frozen extraction sources verified; 67/120 traces fully covered. Read the ignored queue's `sessions/2026-09-09-resume-summary.json` and `provider-limit-probe.json`. The earlier 616-record first-session summary remains intact.
- Schema-retry code is offline-tested but has not been used on production records. API 1 continuation is awaiting the user's choice; do not claim that it has started.
- The server code is validated by 79 offline tests, independent Git-clone/Python 3.12 installation, and a 299,925-pair actual-atom/real-BGE/random-logit export. See `docs/server-matching-validation-20260909.md`. No real Qwen GPU benchmark or matcher accuracy claim exists.
- `exports/medcase24-atoms-partial-20260909.tar.gz` is an ignored, explicitly partial transfer snapshot, not the full study. Never publish it as completed evidence or silently grow its frozen matching node pool.


## Balance-authorized continuation (supersedes the quota pause)

- The user explicitly authorized API 2's available balance for the remaining extraction, estimated around $2, and enabled Use balance in the correct workspace. A successful original request verified the switch; no endpoint/model/configuration change is needed.
- Latest active invocation: `scripts/recover_extraction_schema.py` with the original study/config/output, six workers and a 40-minute session. Check current status/lock; do not start a duplicate. `response.cost` now reports actual balance charges, which should be summed separately from historical subscription allowance.
- All source and metadata extraction records have now completed; remaining work is output extraction/atomization. The schema retry policy is now in use on previously failed stages only. Keep its request-key and per-task audit metadata.
- User supplied local NLI throughput: use 7.25 complete bidirectional pairs/s for planning. `scripts/profile_blocker.py` stores all real BGE/lexical scores/ranks and threshold count profiles. The completed partial profile is in `runs/blocker-workload-20260909/`; rerun on a NEW full bundle/output after extraction completes.
- Current partial bundle (1,157 records): 185,605 default candidate pairs at 0.62/top12, about 7.11 GPU hours. Raising threshold to 0.70 only reduces this to 181,864. This is not the final full-study estimate.


## Extraction complete; server prepared, GPU explicitly deferred

- Latest user instruction: finish currently possible CPU tests, STOP, wait until they report a free GPU. Do not start GPU inference or an automatic idle-GPU waiter. GPU 3 is an 11 GB RTX 2080 Ti; large free memory on busy GPU 1 does not authorize sharing it.
- Extraction now 1,487/1,487 and all 120 trace extractions complete. Actual API2 balance charge $1.88299488. Final hash/lock/coverage audit: queue `sessions/2026-09-09-final-summary.json`. 38,229 mentions, 509 unlocated; location is not semantic accuracy. Eight stages used the audited schema retry. Earlier quota/first-session notes are historical.
- Complete transfer archive `exports/medcase24-atoms.tar.gz`: 30,945 nodes, 20,196,086 possible pairs. Complete BGE profile `runs/blocker-workload-full-20260909/`: default 256,811 bidirectional candidate pairs = 9.84h at user-supplied 7.25/s. Preserve 0.62/top12/batch16/margin5.28, matching old run.sh defaults; no threshold tightening requested.
- Chewie is reachable by ordinary `ssh chewie`, via existing SSH configuration; no Computer Use or Chrome permissions needed. New checkout `~/clinical-factflow`; real data transferred with SCP, not Git. Cache root `/scratch/users/jiajun`, existing interpreter `venv-matcher/bin/python`.
- New launcher `GPU=4 ./scripts/run_server_matching.sh` uses detached tmux, checks physical GPU availability, resolves to UUID and verifies PyTorch mapping. It fails rather than using another card. Only run when user authorizes a later launch; no GPU process has been started in this preparation phase.


## 2026-09-10: two-GPU launch authorized

- User reports physical GPU 0 and 4 idle and explicitly requests splitting data and starting both. This supersedes the previous stop/wait instruction; syncing the prepared launcher is part of the authorized launch. Use these two GPUs only.
- Split whole case inventories by saved default candidate counts, not facts inside a case; preserve the frozen node pool, defaults and both directional judgments. Separate tmux names and output ledgers per GPU. GPU UUID checks remain mandatory.
- `scripts/split_matching_bundle.py` creates disjoint, complete case shards and `plan.json`; each shard retains the complete parent extraction's record provenance and explicitly marks its selected-case scope. Preserve both output directories and the plan for later whole-study analysis.


## 2026-09-10 launch result — GPU 0 running, GPU 4 blocked by a new job

- Commit e5d7c70 was pushed and pulled on Chewie. `exports/medcase24-two-gpu/plan.json` assigns 12 complete cases / 128,210 candidate pairs to gpu0 and 12 / 128,601 to gpu4 (4.91h and 4.93h at the planning rate). Whole-case bytes and ranking pools are unchanged.
- Started tmux `clinical-match-gpu0`, output `/scratch/users/jiajun/clinical-factflow/medcase24-pairs-gpu0`, model PID 918462. Actual physical UUID GPU-afd80b26-8193-fc3a-11cf-c26844f7a619 matched PyTorch, CUDA kernel check passed, BF16 Qwen loaded, and 336 real bidirectional judgments had been saved at verification. Do not confuse initialization logs with completion. Check current process/ledger before any resume.
- GPU 4 was idle at initial inspection but another user's job (dkarzanov, PID 913736) started before our launch. The guard refused to launch gpu4. **No second tmux or automatic waiter is running.** Do not use other GPUs or share GPU 4 without new user guidance. The async question asks whether to wait for a new user notification or queue the second shard on GPU 0; no answer yet at this writing.
- Follow-up must preserve this split; do not run the full bundle on GPU 0 while its first shard is already active. Matching defaults unchanged: 0.62/top12/batch16/margin5.28.


## GPU 1 sharing explicitly authorized (2026-09-10)

- Latest user explicitly chooses to share physical GPU 1 despite the stable ~0.9 GB / ~10% existing job, and requests a check five minutes after launch. This supersedes the no-sharing restriction for GPU 1 only. Do not stop or alter the other user's process.
- `ALLOW_GPU_SHARING=1` explicitly enables sharing in the launcher; UUID binding, CUDA verification and at least 38,000 MiB free remain required. Default launches still reject sharing.
- Second shard remains `exports/medcase24-two-gpu/gpu4` (historical assignment name), 128,601 pairs, but is to run in tmux `clinical-match-gpu1` with output `/scratch/users/jiajun/clinical-factflow/medcase24-pairs-gpu1`. Never also launch its gpu4 copy. GPU 0 continues its separate shard.


## GPU 1 successfully relaunched with Blackwell runtime (2026-09-10)

- User resumed compatibility work and authorized running the second shard on shared GPU 1. Original cu126 preflight failed with no kernel image for sm_120; that attempt exited before matching. Do not mistake its old append-only log entries for a current failure.
- The independent copy `/scratch/users/jiajun/venv-matcher-blackwell` now contains PyTorch 2.14.0+cu130 and sm_120 support. Original `/scratch/users/jiajun/venv-matcher` remains 2.14.0+cu126 for GPU0. All non-Torch package settings, model weights, BF16/batch16/thresholds are unchanged. Compatibility setup finished before the temporary cancellation was checked; the later user explicitly authorized using it.
- Successful GPU1 launch at 2026-09-09 23:58:25 UTC, tmux `clinical-match-gpu1`, results `/scratch/users/jiajun/clinical-factflow/medcase24-pairs-gpu1`, bundle `exports/medcase24-two-gpu/gpu4`. UUID and actual CUDA kernel check passed with sharing_authorized=true. Do not launch the same second shard on GPU4.
- Launch command uses `GPU=1 ALLOW_GPU_SHARING=1 PYTHON=/scratch/users/jiajun/venv-matcher-blackwell/bin/python MATCH_SESSION=clinical-match-gpu1 MATCH_BUNDLE=exports/medcase24-two-gpu/gpu4 MATCH_OUT=/scratch/users/jiajun/clinical-factflow/medcase24-pairs-gpu1 ./scripts/run_server_matching.sh`.
- App heartbeat `gpu-1` is a one-time follow-up around five minutes after successful launch. Read `/scratch/users/jiajun/clinical-factflow/gpu1-launch-baseline.json`, actual ledgers, fresh log tail and tmux/processes. Ignore old cu126 failure. Do not infer other-user training slowdown from GPU utilization alone, and do not create further recurring monitoring without a request.
