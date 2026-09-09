# Revised diagnosis smoke test — 2026-09-09

Two previously inspected MedCaseReasoning cases, one condition: split information with correctly matched specialists. Full synchronous topology, three agents, three rounds. DeepSeek V4 Flash through OpenCode Go, explicitly using API 2. Only generation ran; extraction and matching were not changed or executed.

## Protocol changes

- Every agent is explicitly collaborating on the same patient; separate reports and peer outputs belong to that patient.
- All agents and all five arms share only an opaque study-patient ID, the stated age, and sex as reported. No chief complaint, history, geography or diagnosis is added to this shared block. Original source partitions remain verbatim and disjoint; demographics deliberately repeat information already present in the clinical source.
- The JSON response keeps `assessment` and `answer`, and adds a required, single-line `final_diagnosis` containing one full disease name. `outcome.answer_field: final_diagnosis` controls voting. Explanatory answer strings are no longer compared.
- Every complete round records agent predictions and a system majority outcome. Missing outputs fail; a tied vote abstains. Historical YAMLs/traces retain their original response contract.
- The independent project now has its own local `.env`, mode `0600`, ignored by Git. Configs name `OPENCODE_API_KEY_2`; there is no credential fallback.

## Validation and accuracy

42 offline tests passed. All 120 unexecuted pilot YAMLs passed 1,080 simulated message-visibility/reference-isolation checks. Both live traces completed: 18 successful calls, zero retries/failures, all usage reported. All 18 original outputs were read. No different-patient rejection was observed; the Moyamoya laboratory agent incorporated peers and revised its diagnosis in R2.

Accepted labels were frozen before calls: **Moyamoya disease** and **Phosphaturic mesenchymal tumor**. Only case, whitespace and a trailing period are normalized. This is strict reference-label accuracy, not independently adjudicated clinical correctness. No post-hoc aliases or rationale-based credit were added. Ties count incorrect in system accuracy.

| Round | Agent-level exact accuracy | System-level majority exact accuracy | Tied systems |
|---|---:|---:|---:|
| R1 | 3/6 (50.0%) | 1/2 (50.0%) | 1 |
| R2 | 4/6 (66.7%) | 1/2 (50.0%) | 0 |
| R3 | 5/6 (83.3%) | 2/2 (100.0%) | 0 |

**Remaining semantic distinction:** some final fields select tumor-induced osteomalacia, while the reference names the causative phosphaturic mesenchymal tumor. Their assessments/answers can mention the tumor and still choose the syndrome in the final field. In R2 the syndrome wins 2–1; in R3 the reference tumor wins 2–1. This is a diagnostic-label level difference, not a prose-induced false tie. Requiring one disease name does not solve every synonym or syndrome-versus-etiology issue. The only observed tie was the first-round PMT case with three distinct labels.

This two-case test establishes technical feasibility only. It neither estimates population accuracy nor supports a role-effect claim. The previous ten-run smoke corpus is not pooled into these accuracy figures.

## Measured usage and 120-trace forecast

[OpenCode **Go** official pricing](https://opencode.ai/docs/go/#usage-limits), retrieved 2026-09-09 11:50 UTC: DeepSeek V4 Flash off-peak input $0.22 / output $0.66 / cache-read $0.007 per million tokens. Weekday peaks are 01:00–04:00 and 06:00–10:00 UTC; this test ran 11:49 UTC, off-peak. These are dollar-equivalent subscription allowance costs, not a verified incremental cash charge.

| Measurement | Two completed traces |
|---|---:|
| Input tokens, including cache | 22,501 |
| Cached input tokens | 2,304 |
| Output tokens | 4,751 |
| Go allowance equivalent using reported cache | $0.007595 |
| Conservative cost treating all input as uncached | $0.008086 |
| Generation wall time | 23.25 seconds |

For **24 cases × 5 conditions = 120 traces = 1,080 agent calls**, sequential traces with three concurrent agents within each round:

- Direct two-trace extrapolation, no cache discount: **$0.485**, **23.3 minutes**.
- Adjusting for the historical five-condition cost/time mix: **$0.498**, **25.1 minutes**.
- Practical planning range: **$0.50–$0.80 of Go allowance and 25–40 minutes**; reserve **$1** as a planning buffer. These are estimates, not confidence intervals or enforced spend/time caps. Network problems or provider changes can exceed them.
- Formula for the mixed-condition estimate: historical mean across 10 traces × 120 × (new split-specialist mean / historical split-specialist mean). Historical runs inform cost/time only. Future cases differ, and all estimates assume the same off-peak rates.
- Scope is **diagnosis generation only**. MiniMax extraction/atomization and local Qwen matching are outside this estimate and have not been started.

## Approval and reproduction

**The 120-trace study has not started. Explicit user approval is required before executing it.** Its five-condition YAMLs are prepared with the same corrected protocol. Full-cohort free-text scoring remains ungraded until accepted labels or another verified scoring protocol are frozen; the two-case scoring contract is not silently generalized to all 24 cases.

Local private artifacts: `runs/revised-smoke-20260909/plan.json`, `status.json`, `checks.json`, `diagnoses.json`, `pricing.json`, the archived official Go HTML, `pipeline-source-snapshot/`, and both immutable `traces/` folders. No source cases, responses, keys or call logs are committed.

Preparation configs: `configs/smoke/revised-20260909/`. The local two-case input has predeclared evaluator-only accepted labels. Subsequent stages must use each run’s exact YAML and source snapshot; never rewrite completed runs to conceal defects.
