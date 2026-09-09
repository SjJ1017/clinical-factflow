# MedCase24 generation complete — 2026-09-09

**120/120 case-condition traces completed: 24 cases × 5 conditions, three agents,
three synchronous rounds, 1,080 diagnostic outputs.** This is generation only.
Extraction, atomization, local matching and LLM-assisted grading have not run.

The user approved execution conditional on later level-aware evaluation. The
[three-label evaluation contract](diagnosis-evaluation.md) was saved before this
study started. Primary accuracy will distinguish precise_correct, level_correct
and incorrect, with explicit review flags. No three-label accuracy is claimed in
this generation report. The saved literal majority outcomes remain ungraded
baselines; gold-aware labels will not be used to manufacture a system majority.

## Execution

- Model: DeepSeek V4 Flash, through OpenCode Go, API 2 from this checkout's own
  ignored `.env`. Temperature 0.7, max_tokens 1600, timeout 120 seconds, at most
  three attempts per request, thinking disabled as in the reviewed smoke protocol.
- Full synchronous topology, original source evidence visible every round, all
  own history retained, peer outputs from the immediately preceding round.
- Shared/split × generic/specialist, plus split information with fully mismatched
  specialists. Same patient identity/age/sex block across every agent and arm.
- The frozen hash-shuffled case-condition order interleaved settings. Traces ran
  sequentially, with at most three concurrent agent requests within a round.
- All 120 configured traces were generated fresh. The previous smoke results
  were not inserted into the experiment.
- Started 2026-09-09T12:02:51.270502+00:00; ended 2026-09-09T12:45:26.553918+00:00.

## Completeness, reliability and resources

| Measure | Result |
|---|---:|
| Complete traces | 120/120 |
| Complete agent outputs | 1,080/1,080 |
| HTTP/model attempts | 1,104 |
| Successful API responses (including excluded whole-run outputs) | 1,093 |
| Failed API attempts, retained in audit | 11 |
| Excluded failed whole runs, retried under unchanged YAML | 2 |
| Attempts with missing usage | 1 |
| Input tokens with reported usage (including cache) | 1,698,094 |
| Reported cached input tokens | 150,912 |
| Output tokens with reported usage | 377,440 |
| Known-usage Go allowance equivalent | $0.590547 |
| End-to-end generation study time | 42.59 minutes (including recovery downtime) |
| Median time per trace | 13.51 seconds |
| Longest trace | 231.86 seconds |

Costs use the archived [OpenCode Go official price table](https://opencode.ai/docs/go/#usage-limits):
DeepSeek V4 Flash off-peak input $0.22, output $0.66, cache-read $0.007 per million
tokens. The entire generation interval was off-peak. This is a subscription
allowance equivalent, not a verified incremental cash bill. Failed attempts with
returned usage are included; attempts without usage have unknown cost, not zero.
Missing cache counts, if any, are conservatively treated as uncached for this
estimate and reported in the private audit.

| Condition | Traces | Outputs | Attempts | Known Go allowance |
|---|---:|---:|---:|---:|
| shared-generic | 24 | 216 | 227 | $0.123131 |
| shared-specialist | 24 | 216 | 218 | $0.136973 |
| split-generic | 24 | 216 | 218 | $0.106371 |
| split-specialist | 24 | 216 | 217 | $0.106855 |
| split-mismatched | 24 | 216 | 224 | $0.117217 |

All outputs were checked structurally against the original requests: frozen
configuration/code/data hashes; complete artifact hashes; independent call IDs
and separate agent sessions; exact source/self/peer visibility; shared patient
metadata; reference isolation; final-diagnosis response schema; and per-round
outcome records. These checks establish trace integrity, not clinical correctness.

The 11 failed attempts comprise four schema-validation failures, six incomplete
responses, and one timeout. Failed attempts remain in the call audit and were not substituted into the final
turns. Case-condition runs that exhausted configured retries were retained as excluded
failed runs. Each was rerun in full using the unchanged YAML and a new run ID;
none of its partial outputs were spliced into a completed run. Resource
totals include that failed run, including its successful-but-excluded API responses.
A recovery checkpoint and controller snapshot document the interruption.

Some responses contained nonempty `reasoning_content` despite the request's
`thinking: disabled` setting. One failed run exhausted its 1,600-token budgets on
reasoning with no final content. This is a provider-response limitation, not a
silent change to the configured protocol. The audit lists all 36 responses with nonempty reasoning content;
future efficiency analyses should retain this discrepancy rather than assume
that reasoning was effectively disabled on every call. Formatting/granularity flags, if present, are review candidates rather than
automatic clinical errors. Review flags and all predictions are retained locally.

## Local artifacts

The ignored `runs/medcase24-approved-20260909/` directory contains:

- `plan.json` and `status.json`: approval, frozen order/settings and complete run index.
- `audit.json`: completeness checks, per-condition resources and failed-attempt ledger.
- `diagnoses.json`: all 1,080 final diagnoses with run/case/agent/round keys.
- `traces/`: exact requests, outputs, visible input IDs, usage and references.
- `config-snapshot/`, `pipeline-source-snapshot/`, the case/cohort snapshots,
  `pricing.json` and `diagnosis-evaluation.md`: frozen reproduction material.

No source data, generated traces, credentials or model-call logs are committed.
The source-level extraction and matching settings remain unchanged and unexecuted.

## Adding rounds later

These complete traces can be used as parents for an explicit continuation, without
regenerating R1–R3. The continuation must preserve the original outputs and visibility,
inherit the same reports/roles/memory rules, start at R4, and record parent hashes
in a new run directory. A continuation entry point is not yet implemented; editing
`rounds` in the old YAML is not a supported shortcut.

The existing agents saw `Round 1/3`, etc. A later extension to five rounds is a
three-round-plus-continuation protocol, not an experiment originally announced as
five rounds. Extend all five conditions consistently when comparing them; do not
selectively extend only failing runs and interpret that as a paired comparison.
