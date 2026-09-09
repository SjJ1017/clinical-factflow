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
  split-specialist traces are complete; all 120 main-study traces await explicit
  user approval of the reported cost/time/results. Do not treat a prior request
  to prepare configs as approval to execute them.
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
