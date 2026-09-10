# MedCase24 roles / information report

The user requested an English report covering each of the five conditions, all
three rounds, exact/fuzzy diagnosis accuracy, two graph-based fact counts,
evidence-type entropy, professional output shares and uptake, and directed
previous-round source graphs. The completed artifact is local and ignored:
`findings/medcase24-study/index.html`.

## Rebuild without API calls

```sh
.venv/bin/python scripts/study_report/analyze.py
.venv/bin/python scripts/study_report/build.py
node scripts/study_report/check.cjs findings/medcase24-study/index.html
```

The inputs are the sealed 120-run viewer payload and completed name-judge sidecars
under `runs/medcase24-name-judge-20260910-v2/`. The builder does not change the
extractor, matching threshold, original annotations or diagnostic runs. The older
matching report's complete-link counts remain a different explicitly named metric.

## Units and definitions

- Whole-trace totals have both output-only and outputs-plus-initial-materials scopes.
- Equivalence counts use connected components of direct equivalence edges.
  Entailment counts use weak components of equivalence plus either directional edge.
  Weak components are related content groups, not guaranteed synonymous facts.
- Round counts use the induced graph on the round's panel outputs. New counts use
  prefix graphs, with earlier outputs alone or initial material plus earlier outputs
  as the prior set. Future atoms do not provide bridging paths. Later component
  mergers mean online new counts need not sum to the final component count.
- Loyalty defaults to within-set equivalence components; exact text/qualifier atoms
  are an alternative. Component domains are the union of member occurrence domains
  in that particular input/output set. This does not add or change atomic labels.
- Clinical = history/examination; laboratory = laboratory/pathology; imaging =
  imaging. Diagnosis/treatment/other remain shared. They are in the output denominator
  and in fractional label denominators, but are not another profession.
- Inclusive weighting counts both own and other when both appear. Fractional weights
  divide matching original labels by all labels; e.g. imaging+diagnosis contributes
  0.5 imaging, 0 other profession, 0.5 shared. Own minus pooled-other output share has
  no universal zero baseline with three professions.
- Input uptake uses the deduplicated union of actually delivered sources, common
  metadata, self history and peer outputs. Source graphs use only each of the three
  immediately preceding outputs, checked against actual delivery IDs. Self loops and
  peer arrows are both shown. Edge categories follow the **receiving** profession.
- Uptake accepts exact identity or a direct equivalent pair; an optional mode accepts
  input-entails-output. Reverse entailment is not uptake in that mode. An input unit
  counts once if any member directly matches output. A zero denominator is NA.
- Ratios are computed per case/agent first. The all-role summary averages agents
  within case before averaging across cases. Paired contrasts resample 24 cases,
  2,000 replicates with a fixed seed; no multiplicity adjustment is claimed.
- Generic/split roles follow partition allocation; generic/shared gets the same
  virtual role assignment as matched specialists for that case. Mismatched roles
  follow actual role prompts. The auxiliary peer-excess check compares own-field
  output share with other agents' share of the same field, avoiding unequal domain
  prevalence being mistaken for broken generic-agent symmetry.

## Low-cost name judging

Latest user explicitly authorized API 2 balance under USD 0.10, no reasoning and
short context. This supersedes the older full-case judge-input requirement for this
**name-only** report, not for a future case-supported clinical adjudication.

- MiniMax M3, OpenCode Go `/messages`, `thinking: disabled`, temperature 0,
  max output 512 tokens, up to 12 unique name pairs per request.
- Names only: no patient context, reference reasoning, condition or role labels.
  Pair order is symmetric. Input names can serve diagnosis grading or reference-blind
  within-panel synonym comparison; grading labels never determine a panel winner.
- Exact = normalized string identity (casefold, whitespace, trailing period).
  S = same-specificity synonym; L = explicit taxonomic refinement; D = different;
  U = unresolved or potentially causal association requiring case information.
- Fuzzy primary is S. Optional S+L is name-level compatibility, not proof that the
  patient's evidence supports a subtype or cause. U and abstentions stay in the
  denominator with no point credit; they are separately reported.
- Preserve literal voting; optional semantic voting merges only same-level S labels
  among actual agent names, never level/cause matches. An inconsistent two-edge
  synonym triple abstains. Representative choice is reference-blind.
- The first permissive pass is retained in `...-20260910/` and retracted for this
  report. The entire 278-pair set was judged again with the revised rubric. One
  malformed response echoed names in each row; its attempt is retained and billed.
- Final raw model labels are immutable. `review.json` holds 13 explicit corrections
  or unresolved flags, with sources for important hierarchy distinctions. All S/L
  labels were inspected; D/U labels remain model-provisional. This is assistant
  review, not clinician validation.
- Total estimated Go-valued usage across both passes and the failed-format attempt:
  USD 0.02182356. No returned thinking blocks. Prices verified from the official Go
  page (input 0.30, output 1.20, cached read 0.06 USD per million tokens). This is
  usage-based costing, not a separate workspace-balance invoice reconciliation.
  Every dispatch reserves a conservative byte-based input bound plus maximum output,
  with all earlier version costs included before applying the USD 0.10 ceiling.

Do not rerun `judge_names.py` merely to rebuild a report. Reuse completed sidecars.

## Verification

Offline JavaScript checks cover every report control family, both weighting rules,
all graph transitions and conditions. Synthetic tests verify overlapping labels,
fractional weights, directionality, NA denominators and graph-scope restriction.
Data-level assertions check all 120 traces / 1,080 outputs, 8,640 profile rows,
17,280 source-graph observations, 1,800 accuracy observations, bounded uptake and
novelty counts. Exported graph SVGs were rasterized and visually checked for arrow
and label placement. This is not a real-browser layout audit; the browser's prior
local-file URL denial was not bypassed.
