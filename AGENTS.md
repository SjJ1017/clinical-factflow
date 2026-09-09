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
