# MiniMax M3, thinking disabled: extraction accuracy audit — 2026-09-09

M3 now has results for all ten prespecified texts. Its returned quotes locate perfectly, and its measured latency is much lower than M2.5. **Quote location is not semantic accuracy**: temporal scope, joint diagnostic grounds, domain omissions and duplicate extraction remain material problems.

## Protocol

The user requested M3 with thinking disabled and an accuracy check. The eight remaining texts were processed using `configs/extraction/minimax-m3-speed-v4.yaml`; the already completed S03/S04 results were reused rather than regenerated. Same input text, prompts, annotation schema and `candidates_v1` selector as the previous comparison. Only model and thinking setting differ from M2.5. Both M3 batches have byte-identical saved configs and pipeline sources; output artifact hashes were checked before review. M3 uses OpenCode Go API 2, `thinking: {type: disabled}`, temperature 0, max tokens 8,000, timeout 120 seconds, three attempts and a six-worker limit. Only selected parents enter atomization.

The ten texts are five complete agent outputs (875 words), four source segments (110 words), and one common-metadata text (10 words). This is an extraction audit, not diagnosis evaluation; the original speaker's clinical diagnosis is not judged against the case answer key.

Private evidence:

- `runs/minimax-m3-speed-pilot-20260909/`: the two previously tested outputs.
- `runs/minimax-m3-accuracy-completion-20260909/`: eight new results and all calls, config, source, pricing and timing snapshots.
- `runs/minimax-m3-accuracy-review-20260909/`: `audit.json` contains every M3 and M2.5 mention's review status and issue notes, `review.md` is the readable comparison, and `protocol-check.json` records artifact consistency.

Raw case text and model outputs remain ignored. Original results were not corrected or overwritten. No full-corpus extraction, matching or diagnosis judging ran.

## How accuracy was assessed

Codex reviewed every final mention against its target text, unblinded to model. This is an assistant audit, **not independent clinician annotation, external judge consensus or an established gold benchmark**.

Three independent metrics:

1. **Quote location:** at least one occurrence is an exact substring of the target.
2. **Fidelity:** text plus qualifiers preserve what was asserted, including numeric, time and conditional scope. Losing a shared symptom duration or turning jointly definitive/exclusionary grounds into independently definitive/exclusionary grounds is an error. Distributing weaker `support`/`given` grounds is a review case, because ordinary-language support may or may not be distributive. More-specific specimen provenance with unclear grounding is also a review case.
3. **Domain set:** no identified missing or unsupported label under the frozen multilabel rubric. A diagnostic interpretation based on a lab result needs both domains; a past/chronic lab result does not automatically require history. Undefined anatomical modality and vague clinical presentation remain review cases. Suggested diagnostic workup is not treated as a treatment intervention solely because it is a recommendation.

The strict pass rate is **pass / all mentions**, keeping review cases in the denominator. It is not `1 - obvious-error-rate`: uncertain cases are not counted as correct. Counts are per model's final mentions, so model-specific granularity and duplicates affect the denominator. Compound, unresolved and duplicate flags are reported separately; a faithful compound can pass fidelity while still failing atomicity. Full recall and accuracy of all other annotation axes were not scored. Medical correctness of the original outputs was not scored.

## Paired-text results

| Metric | M2.5 output-only candidates | M3 thinking disabled |
|---|---:|---:|
| Final mentions | 165 | 194 |
| Exact quote location | 159/165 (96.4%) | **194/194 (100%)** |
| Strict fidelity pass | 140/165 (84.8%) | **174/194 (89.7%)** |
| Fidelity: clear errors / review cases | 14 / 11 | **10 / 10** |
| Strict domain-set pass | 130/165 (78.8%) | **163/194 (84.0%)** |
| Domains: clear errors / review cases | 29 / 6 | **24 / 7** |
| Observed additional duplicate mentions | 2 | **13** |
| Flagged residual compounds | 17 | 15 |
| Flagged unresolved references | 12 | 17 |

This table does not establish a statistically reliable model ranking. It is a small, unblinded review of different fact sets on the same texts. In particular, M3's increase from 165 to 194 mentions is partly duplicate extraction rather than improved coverage. The old M2.5 qualitative audit was rescored under the same explicit rubric for this table; it is not being compared with the earlier context-contaminated v1 pilot.

Within M3:

| Channel | Mentions | Strict fidelity pass | Strict domain-set pass |
|---|---:|---:|---:|
| Agent output, five texts | 168 | 153/168 (91.1%) | 138/168 (82.1%) |
| Original source, four texts | 23 | 18/23 (78.3%) | 23/23 (100%) |
| Shared metadata, one text | 3 | 3/3 (100%) | 2/3 (66.7%) |

The source fidelity failures all come from lost shared symptom durations in one history segment; source-domain results alone therefore conceal a real fidelity problem. The metadata domain review concerns the opaque patient identifier, for which the current ontology has no dedicated label. Neither tiny stratum gives a population accuracy estimate.

## What went wrong

These are illustrative paraphrases, not new case data:

- **Joint certainty strengthened:** an output saying that clinical findings AND imaging jointly establish a diagnosis became two claims that each independently establishes it. This is a semantic change despite a perfectly located quote. Joint exclusion has the same problem. We kept weaker support distribution separate as uncertain, rather than calling every such split definitely wrong.
- **Time scope detached:** a shared duration applying to a symptom list remained on the first symptom but disappeared from later children. The quote can still contain the duration while the atom text and qualifiers omit it.
- **Evidence domains omitted:** a statement connecting an antibody result to a diagnosis received only `diagnosis`, or a lab-supported diagnostic claim received only `laboratory`. Multiselect support works structurally; label completeness still fails.
- **Duplicates and unresolved summaries:** some observations were emitted once as a list expansion and again as paraphrases. Thirteen additional duplicates were identified; semantic near-duplicates may remain. Vague `these findings`/`the diagnosis` references also persist.
- **Other fields need separate evaluation:** some causal interpretations were labeled `observation`; the present fidelity/domain percentages do not certify `kind`, `certainty`, `attribution` or polarity accuracy.

No recurrence of the known v1 input-only facts was observed. This does not make source faithfulness automatic: hallucinated specificity, omissions and scope changes can occur with an output-only boundary too.

## Time and allowance

- Eight new texts: **21.26 seconds batch elapsed**, six workers, no retries.
- Earlier two texts: **20.56 seconds batch elapsed**, two active workers, no retries.
- Combined ten-text corpus: **18 successful calls, zero failed calls, zero returned thinking blocks**, 21,887 API output tokens.
- Total known Go allowance: **$0.03616**, including the earlier two texts; this turn's eight cost about **$0.02542**. Rates were fetched from [OpenCode Go](https://opencode.ai/docs/go/) and archived per batch. Some responses omit cache fields, treated as zero for estimation; this is not a reconciled cash bill or proof of absent provider-internal computation.

There was no new simultaneous ten-text run: do not report the eight-text 21.26 seconds as the measured wall time of all ten. Sum of record durations across all ten is 137.13 seconds; full-output records average 19.91 seconds.

For 1,080 outputs plus 383 unique source records and 24 unique metadata records, six-worker linear extrapolation gives **1.14–1.24 hours**, comparing per-record with per-word scaling. About **1.5–2 hours** is a planning allowance for overhead and possible retries, not a confidence interval or quota guarantee. Known allowance projects **$6.78–7.42**. This assumes provenance-preserving cross-run evidence reuse, which is still not implemented in the naive per-run entry point; it excludes matching and diagnostic judging. No retries in 18 calls does not establish sustained reliability.

## Operational decision

The user's selected extraction model is now **M3 with thinking disabled**. Reusable root YAMLs adopt that extraction model and setting; generation remains DeepSeek and historical run configs are immutable. The `minimax-m3-speed-v4.yaml` measurement config remains frozen. These results justify continued M3 use for extraction development, not a claim of gold-standard accuracy or permission to launch the entire study's extraction.

The most useful next corrections are preserving joint premises and shared scope, reducing duplicate expansions, and applying the existing domain rubric consistently. These require no extra atom attributes. No prompt changes were mixed into this comparison.
