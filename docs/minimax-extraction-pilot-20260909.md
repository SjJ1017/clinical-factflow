# MiniMax extraction pilot — 2026-09-09

The small pilot completed, but the current extraction protocol is **not ready for a full trace corpus**. Direct source text generally worked in this sample. Agent-output extraction had context-only imports, imperfect exact quotes, and missing evidence-domain labels in diagnostic claims. Low API cost does not establish measurement validity.

## Scope and measurement boundary

Ten texts were selected before observing MiniMax output: one output from each of the five experimental conditions across three cases and rounds 1–3, four original evidence segments, and one common-metadata record. This is a purposive coverage check, not a representative benchmark or a condition-effect comparison. Each condition has only one output sample.

All 162 final mentions were inspected by Codex against the original target text and, where needed, its saved visible input. This is a text-based audit, **not independent clinician gold annotation**. Domain review records clear mismatches separately from boundary/under-specification cases; it is not a validated accuracy score. Recall was not exhaustively annotated.

The atom fields are unchanged. `annotation.clinical_domain` alone becomes a nonempty list of the existing eight domain values; no truth, importance, causal-graph or outcome attributes were added. Existing other annotation axes were retained but not systematically evaluated. The domain rubric and split/no-split examples are in `configs/extraction/minimax-pilot-20260909.yaml`.

Agent inference remains DeepSeek. Both extraction passes used **minimax-m2.5**, OpenCode Go API 2, the documented Anthropic `/messages` transport, temperature 0, max output 8,000, timeout 120 seconds, up to three attempts, batch size 20 and parallelism 1. There were no mid-pilot prompt or limit changes.

This is a separate `clinical-domain-multilabel-v1` measurement stage over frozen generation artifacts. The 120 completed generation YAMLs and traces were not rewritten. Parent artifact/config/source-snapshot hashes and new extraction code/config/input hashes are recorded separately. The old DeepSeek smoke annotations are not pooled with this pilot.

## Exact quote location

An atom counts as located when at least one of its retained quote occurrences matches the target text exactly. This does not by itself establish that the quote entails the whole atom.

| Text channel | Final mentions | Located | Rate |
|---|---:|---:|---:|
| Agent output | 135 | 110 | 81.5% |
| Original evidence | 24 | 24 | 100% |
| Shared metadata | 3 | 3 | 100% |
| Total | 162 | 137 | 84.6% |

Occurrence-level accounting is 139/164 located (84.8%); the extra occurrences come from within-record duplicates. Initial parent quotes were 101/108 located. These stages have different denominators because atomization changes granularity.

Of the 25 unlocated final mentions:

- **20 are input-only imports**, all in S04 (split-specialist, R3). Tumor dimensions, detailed tissue/marker findings and prior reasoning were available in the reference context but absent from the current output. Six initial parent texts account for 19 final mentions; a context-only symptom in another parent’s `qualifiers` was promoted by atomization into the twentieth. This qualifier path was clarified in the [follow-up audit](minimax-context-and-thinking-20260909.md).
- **5 are quote-construction failures for target-supported content**: rewritten phrasing, expanding a shared modifier into a nonexistent contiguous span, or replacing a pronoun with its referent inside the quote. One was already present in the first pass and four appeared during atomization.

These 20 imported facts may concern the same patient and may be true; the defect is attributing them to an output that did not express them. They would artificially inflate output coverage, persistence or transmission. No extracted outputs were silently corrected or dropped.

## Content-domain review

Across 162 final mentions, the audit flagged **24 clear domain omissions/misclassifications** and **12 boundary or under-specified cases**. All 24 clear problems were in agent-output samples. Ten mentions used multiple domains. These counts judge labels against the expressed proposition; a plausible label on one of the 20 context-only imports does not make that extracted occurrence valid.

The main failure was dropping the evidence domain when a proposition evaluates its diagnostic significance. For example, the following is a **synthetic illustration**, not a dataset excerpt: a claim that an antibody result supports diagnosis X needs laboratory + diagnosis, but diagnosis alone discards the evidence domain. Similar omissions occurred for imaging, symptom history and treatment response. One proposed diagnostic evaluation was labeled treatment although no therapy was proposed.

Pure laboratory and tissue observations were usually correctly separated in this sample; pathology was not automatically labeled laboratory just because the source allocation grouped them together. The short source example connecting negative imaging to an unlikely diagnosis correctly received imaging + diagnosis. Multilabel output is technically supported but not consistently complete.

Boundary cases include a named syndrome described as an imaging finding, an opaque study ID as history versus administrative metadata, and unresolved phrases such as “these findings” that hide which evidence domains an atom concerns. They were not forced into the clear-error count.

## Other observed defects relevant to matching

- Some independently assertable lists remain bundled after the second pass.
- Some children still contain unresolved references or lose a site/temporal qualifier.
- One atomization dropped explicit marker results while retaining only the statement that the findings were supportive.
- A joint evidence-to-diagnosis statement was split into stronger, independently sufficient claims. These are changes in meaning, not harmless quote-location issues.

These observations are not an exhaustive atomicity or recall error rate.

## Per-text audit

| Sample | Condition / channel | Case | Round | Parents → mentions | Located mentions | Clear domain issues | Boundary cases |
|---|---|---|---:|---:|---:|---:|---:|
| S01 | shared-generic | PMC9867851 | 1 | 22 → 31 | 30/31 | 4 | 1 |
| S02 | shared-specialist | PMC10825882 | 2 | 10 → 18 | 17/18 | 2 | 6 |
| S03 | split-generic | PMC12000239 | 2 | 22 → 25 | 25/25 | 10 | 1 |
| S04 | split-specialist | PMC10825882 | 3 | 16 → 40 | 18/40 | 3 | 1 |
| S05 | split-mismatched | PMC9867851 | 3 | 12 → 21 | 20/21 | 5 | 2 |
| S06 | source | PMC9867851 | — | 8 → 8 | 8/8 | 0 | 0 |
| S07 | source | PMC9867851 | — | 5 → 6 | 6/6 | 0 | 0 |
| S08 | source | PMC10825882 | — | 3 → 3 | 3/3 | 0 | 0 |
| S09 | source | PMC10825882 | — | 7 → 7 | 7/7 | 0 | 0 |
| S10 | initial | PMC12000239 | — | 3 → 3 | 3/3 | 0 | 1 |

## Measured time and allowance usage

| Stage | Successful / attempted calls | API wall time | Go usage estimate |
|---|---:|---:|---:|
| Extraction | 10/11 | 4.89 min | $0.03493 |
| Atomization | 12/12 | 5.85 min | $0.04171 |
| Total | 22/23 | 10.74 min | $0.07663 |

Tokens reported across **all attempts**, including the failed one: 47,853 non-cache input, 13,833 cache-read input, zero reported cache-write input, and 51,207 output tokens. Native Anthropic input tokens exclude separately reported cache tokens; they were not double-counted. Output usage includes provider reasoning, but there is no reliable separate reasoning-token total in these responses.

The single failed extraction attempt reached 8,000 output tokens after 95.9 seconds; its response contained a long thinking block and a truncated formal answer. The unchanged retry succeeded. Atomization succeeded on all 12 attempts. End-to-end 10.74 minutes includes the serial API pipeline and local serialization, not setup or manual review.

Rates were fetched from [OpenCode Go](https://opencode.ai/docs/go/#usage-limits) at 2026-09-09 13:14 UTC: MiniMax M2.5 input/output/cache read/cache write = $0.30/$1.20/$0.06/$0.375 per million tokens. No MiniMax peak/off-peak distinction is listed. The saved page and parsed row are in the private study directory.

The $0.07663 is a **Go subscription dollar-equivalent allowance estimate**, not a verified incremental cash charge. Twelve responses omitted cache-usage fields; those missing fields were treated as zero for this estimate and are explicitly counted in the audit. No account-balance reconciliation was performed.

## Practical decision

Keep the minimal atom structure. Do not use this pilot as a clean measurement corpus or proceed to full extraction on the assumption that changing to MiniMax resolves grounding. The narrow next validation target is input/output separation, exact quote preservation through both passes, and evidence-domain retention in diagnostic propositions. No new atom attributes are necessary. No full extraction, matching or diagnostic judging was started in this task.

## Artifacts and reproducibility

Private artifacts: `runs/minimax-extraction-pilot-20260909/`.

- `sample.json`: the ten preselected target texts and exactly their allowed reference context.
- `extraction-config.yaml`, `plan.json`, `parent-provenance.json`, `source-hashes.json`, and `pipeline-source-snapshot/`: independent measurement provenance.
- `calls/` and `results/`: every API attempt, first-pass parents, atomized children and quote locations.
- `audit.json` and `manual-review.md`: per-mention review linked to untouched raw results.
- `pricing.json`, `go-pricing-source.html`, `index.json`: observed rates, timing and attempt-level accounting.
- `preparation-script.py`, `execution-script.py`, `audit-script.py`, `review-notes.json`: exact pilot preparation/execution/review logic. These are archived execution records, not a resume command; rerunning requires a new study directory.

No case text, generated trace, credential or API cache is committed to Git. Code, versioned configuration and this aggregate report are tracked.
