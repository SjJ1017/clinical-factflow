# Diagnosis evaluation contract — frozen before the 120-trace study

Approved by the user on 2026-09-09. This is a post-generation, LLM-assisted
assessment protocol. It does not change any diagnosis prompt, source partition,
model setting or frozen trace. Exact string matching is a diagnostic baseline,
not the primary correctness criterion.

## Three outcome labels

- **precise_correct — 精准答对:** The final diagnosis identifies the same disease
  at the reference's clinically relevant level. Established synonyms, spelling
  variants and unambiguous abbreviations count here; verbatim identity is unnecessary.
- **level_correct — 层级差异但答对:** The final diagnosis describes the same
  case-supported diagnostic process at a different level, for example its specific
  syndrome versus its established cause, or a justified parent/subtype difference.
  The relationship must be explicit and clinically compatible with the case and
  reference reasoning, with no conflicting etiology or unsupported specific subtype.
  Merely sharing a symptom or broad category is insufficient. Record the direction
  and what diagnostic detail is missing or extra.
- **incorrect — 答错:** A different/incompatible disease, an unsupported subtype,
  or an answer so nonspecific that it does not identify the reference diagnostic
  process. A reference diagnosis listed only among rejected alternatives does not
  earn correctness credit.

Ambiguous reference material or judge uncertainty sets `needs_review: true` and
may leave the provisional label null. This is an unresolved review state, not a
fourth diagnostic category and not a silently incorrect result. Report unresolved
counts explicitly; do not hide them by shrinking denominators.

## Judge inputs and audit

Use a separate, frozen evaluation YAML specifying provider, model, prompt,
temperature, schema and source hashes when the evaluation is actually executed.
LLM judgments are provisional and must be inspectable. Keep the raw response,
label, short rationale, cited prediction/reference excerpts, level relationship,
confidence/review flag, usage and latency as a sidecar keyed by run/case/turn.

The judge receives the final_diagnosis, the complete original case presentation,
reference diagnosis and reference reasoning. It does not receive condition, role,
seat or topology labels. The complete presentation provides an end-task target;
first-round split-information errors remain a separate question from whether the
agent reasonably used its limited input. Neither gold nor judgments are fed back
to the diagnostic agents.

The scoring target is the final diagnosis. Assessment/answer text may be inspected
in a separately recorded review to clarify an abbreviation or ambiguity, but cannot
replace a clearly wrong final diagnosis just because the correct disease appears
somewhere in a differential. Record final-versus-explanation inconsistency separately.

Worked cases:
1. Reference myocardial infarction; final heart attack -> precise_correct.
2. Reference a phosphaturic mesenchymal tumor causing tumor-induced osteomalacia;
   final tumor-induced osteomalacia -> level_correct if the case and reference
   actually establish that relationship. Retain the lost etiologic specificity.
3. The same reference; final primary hyperparathyroidism -> incorrect.
4. Reference a known disease subtype; final a different incompatible subtype ->
   incorrect, not level_correct merely because both share a parent disease.
5. Reference phosphaturic mesenchymal tumor; final a tumor -> incorrect because
   a generic category does not identify the diagnostic process.
6. Reference myocardial infarction; final chest pain -> incorrect; a symptom
   alone is not a diagnostically adequate hierarchy match.

Review every flagged judgment and a fixed, condition-balanced random sample of
unflagged judgments, including precise_correct/level_correct/incorrect. Preserve
initial and reviewed labels, reviewer provenance and disagreement counts. Do not
present unreviewed LLM labels as clinician-validated ground truth.

## Aggregation and reporting

For every round and condition, report precise_correct, level_correct and incorrect
separately, plus **strict accuracy = precise_correct / total** and
**inclusive accuracy = (precise_correct + level_correct) / total**. Show review
coverage and unresolved counts. Preserve case pairing across the five conditions;
three agents from the same case are not three independent patient samples.

Keep each saved literal majority as an immutable baseline. Any semantic majority
must be computed separately and **without reference answers, reference reasoning,
condition labels or access to reports not in the agent outputs**. Canonicalize
unambiguous same-level synonyms before voting; no gold-guided tie resolution.
Parent/child and syndrome/etiology relationships remain visible and are not silently
converted into exact equivalence. A remaining tie is an abstention and is reported
separately, with no correctness credit. Evaluate the resulting system prediction
using the same three-label rubric; do not construct a system answer by counting
how many agents the gold-aware judge labels correct.

If a broader diagnostic-family agreement metric is later introduced, name it
separately and freeze its reference-blind aggregation rules before scoring. Never
publish it as the same quantity as exact-disease majority accuracy.

## Execution boundary

The user's approval authorizes **24 cases × 5 settings = 120 diagnosis traces**,
three rounds and three agents, via API 2 / DeepSeek V4 Flash on Go. The reviewed
same-patient generation protocol remains unchanged. Extraction, atomization,
local matching and paid post-hoc judging are not part of this generation run.
The present execution records all material needed for this evaluation; it does
not claim that the LLM judge has already been implemented, run or validated.
