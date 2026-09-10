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

## Follow-up: outcome, source correctness and mismatch

`analyze.py` now calls `followup.py` after the original analysis. For an existing
base analysis, rerun only `followup.py`, then `build.py`. Both are entirely offline.
Additional checks: `.venv/bin/python scripts/study_report/check_followup.py`.

- The outcome axis spans 0–100%; there is no 50% normalization or ceiling. R3
  synonym-majority S accuracy ranges from 37.5–50%, versus 62.5–79.2% for S+L.
  Six cases earn S in all five conditions, seven earn S in none, and eleven vary.
  L/U/non-credit cannot automatically be interpreted as clinically wrong answers.
- Source correctness uses the existing reviewed name labels, never new model calls.
  Default S+L sources are compared with D sources; U and abstentions are excluded.
  S-only sensitivity also excludes L. Each source's immediately following self and
  two peer outputs must actually contain its output in their visible context.
  Measure total retained source units / total source units, average the two peers
  within source turn, and then average within case. These are separate retention
  opportunities, not exclusive attribution or a probability for independent facts.
- The primary adjusted association compares correct and D sources within the same
  case × condition × source round, then averages those contrasts within case before
  bootstrapping cases. Only mixed-label panels enter; role/information assignment
  remains a possible confound. Default R1 has 42 mixed panels / 15 cases, whereas
  R2 has only 6 / 5. Descriptive group means and matched-panel differences target
  different populations and must not be subtracted interchangeably.
- Default R1→R2 within-panel differences: self +10.31 pp [2.20,18.16], peers
  +7.37 pp [3.37,10.97]. Restricting to profession-tagged units reduces the peer
  difference to +3.41 pp [0.31,6.35]. That subset excludes units tagged only as
  diagnosis/treatment/other; it is not a newly adjudicated pure-evidence subset.
- Mismatch has two explicitly separated alignment questions. The same-case
  matched split-specialist run supplies (a) the same-information/same-seat agent
  and (b) the same-prompted-role/different-seat agent. Eight-tag output composition
  uses total-variation distance. R3 role-distance minus information-distance is
  +0.0264 [0.0074,0.0451]: slightly closer to the information-aligned reference.
  Exact-node Jaccard sensitivity is reported separately; no missing cross-run
  semantic pair is inferred from a trace-local score list.
- The alternative whole-condition comparison uses split/generic with the same
  information versus shared/specialist with the same role. Its R3 composition
  difference is +0.0230 [-0.0004,0.0450], inconclusive. By contrast, the distance
  between per-case three-role mean uptake primes favors shared/specialist:
  role-distance minus information-distance −4.64 pp [-8.12,-1.35]. Mean R3 prime
  is +3.47 pp for mismatch, −4.48 for split/generic and +2.44 for shared/specialist.
  Prime-distance analysis requires all three agent primes in all three conditions
  to be defined; missing R1 professions must not change the compared case mean.
  Composition and uptake selectivity are different observed states, not a single
  causal decomposition of information and role effects.
- Scatter plots show five fixed condition rows and three horizontally aligned round
  panels on a shared −100…100 pp axis. Each colored point is a case-agent prime;
  role means/CIs and case-mean overall means/CIs are separate. Missing denominators
  stay NA. Default R1 has 10 NA in each matched split condition and 39 in mismatch;
  all R2/R3 rows have 72 defined points. Jitter is deterministic across rounds.
- `followup-observations.json` contains 11,520 source uptake rates and 864 aligned
  comparisons for each alignment design. `summary.json` and the standalone HTML
  include all controls, raw scatter points and case-cluster intervals. Additional
  API cost is zero. Bootstrap intervals remain exploratory, without multiplicity
  correction or clinician validation of D/U labels.

Follow-up verification covers explicit NA plotting, 72 unique case-agent records
per condition/round/control combination, three balanced profession colors,
case-cluster weighting, mixed-panel eligibility, and different-seat role alignment.
All eight scatter-control variants and 32 correctness-control variants are checked
alongside the original 324 UI configurations. Three exported scatter SVG panels
were rasterized for visual inspection; no browser-policy workaround was used.

## Outcome strata and majority/minority follow-up

Run `scripts/study_report/social_uptake.py` after the previous analysis, then rebuild
the HTML. `analyze.py` now includes this step automatically. The optional `report`
dependency group adds SciPy for Student-t interval sensitivity. All matching and
name labels are reused offline; no additional API charge or extraction occurs.
Verify with `scripts/study_report/check_social.py` plus the existing JS check.

The new section 07 contains separate controls for condition, S versus S+L grading,
all/profession-tagged source facts, atom/equivalence units, matching direction and
seven uptake/agreement outcomes. Its tables expose counts before pairing, paired
panels/cases, recipient coverage, bootstrap CIs and t sensitivity CIs.

### Definitions and identification limits

- Source correctness is the source agent's diagnosis-name compatibility with the
  reference. It does **not** label each source fact true or false. Default positive
  is S+L, negative is D; U/abstention are excluded. S-only also excludes L.
- Final outcome is the R3 reference-blind synonym-majority label. Final-compatible
  and final-D strata are disjoint traces but can share a case across conditions.
  The all-outcome stratum includes source contrasts with unresolved final grading.
- Correct-minus-D contrasts compare source ratios within the same case, condition
  and source round, then average those panel contrasts within case. Source group
  means in these tables use precisely the same eligible panels. Only panels with
  both groups identify a contrast; absence is NA, not zero.
- Minority-minus-majority compares the single dissenting source with the mean of
  the two agreeing sources. Exactly one of the three within-round diagnosis pairs
  must be S. Three-way disagreement, unanimity and nontransitive label triples are
  excluded. Reference labels never define majority membership.
- Self uptake uses the source's own next output. Peer uptake averages the two
  recipients within source. Cross-opinion uptake uses only recipients whose prior
  diagnosis differs; it avoids counting a majority source's already-agreeing peer.
  Previously unexpressed uptake excludes source units directly matched by the
  recipient's prior output from both numerator and denominator. This measures new
  expression, not whether a fact was unknown or absent from the recipient's context.
- Next-diagnosis agreement is a separate name-level outcome, with self/peer/
  cross-opinion variants. It is not causal copying. Use only identical names or
  existing judged name pairs; unknown pairs remain NA, with coverage disclosed.
  Fact-unit/matching/scope controls do not affect diagnosis-only results.
- Each case, rather than each agent, fact, or trace, is an inference cluster. The
  t sensitivity interval uses the SD of case-mean contrasts and n−1 degrees of
  freedom. It is not clipped to parameter bounds and relies on a sampling model.
  n<2 has no interval. Neither t nor nonparametric bootstrap is reliable population
  evidence with only 2–3 cases. The final-outcome interaction uses joint case
  resampling to preserve overlap between strata, not separate independent CIs.
- Conditioning on a downstream final outcome can induce selection/collider
  associations. A sign reversal cannot identify subjective belief as its cause.
  Current majority is an observable agreement proxy, not a latent belief measure.
  There are no eligible S+L-correct-minority versus two-D-majority panels in this
  pilot at either source round, so the decisive truth-versus-majority conflict is
  not identified. All three final-error mixed-correctness R1 panels are three-way
  disagreements under the strict S-equivalence rule.

### Results under default equivalence matching and all source facts

All differences below are percentage points. Bootstrap intervals are case-level.

- R1→R2, final-compatible runs: correct-minus-D self retention +12.21
  [4.84,19.62], peers +8.99 [6.04,11.82], from 39 panels / 14 cases.
- R1→R2, final-D runs: self −29.86 [−53.04,11.08], peers −9.42
  [−14.29,−4.74], from only 3 panels / 3 cases. Peer t interval is
  [−21.28,2.44]; the negative bootstrap interval must not be represented as robust
  evidence. Restricting to profession-tagged facts gives −2.53 [−5.36,0.37].
- R2→R3 has zero final-D panels containing both a compatible and a D source.
  The sign reversal cannot be assessed again at this transition.
- Overall strict 2:1 panels: R1 has 36 panels / 19 cases; R2 has 21 / 13.
  Minority-minus-majority peer uptake is −3.93 [−8.54,0.51] at R1→R2 and
  −7.08 [−10.32,−3.97] at R2→R3. The latter t interval is [−10.76,−3.40].
  R2→R3 self retention is −13.11 [−18.85,−7.36].
- At R2→R3, cross-opinion peer uptake is −6.90 [−11.07,−2.66]; previously
  unexpressed uptake is −9.22 [−13.62,−4.89]; profession-tagged peer uptake is
  −4.65 [−8.14,−1.08]. The minority disadvantage is not solely an already-agreeing
  majority peer repeating shared content.
- R2→R3 final-D 2:1 panels show the same direction: peer gap −5.70
  [−14.25,3.92], 9 panels / 7 cases. This is directional but uncertain, and does
  not imply that the minority was correct (that conflict is absent).
- Among cross-opinion recipients, next-round diagnosis agreement favors majority
  sources substantially: minority-minus-majority −49.34 [−76.97,−17.76] at
  R1→R2 and −57.69 [−82.69,−30.77] at R2→R3. These are answer convergence
  outcomes, not atomic-fact uptake. All selected 2:1 name comparisons are covered
  by saved labels; no additional judging was needed.

Treat intervals crossing zero with a directional mean as candidate effects for
preregistered replication. More independent cases improve precision conditional on
an effect persisting; 1k/10k traces or repeated draws from the same 24 cases cannot
by themselves guarantee significance or resolve confounding. Do not extrapolate
statistical significance as if the larger experiment had already been run.

The ignored `social-uptake-observations.json` retains 240 source panels, 17,280
source-recipient edges (including numerators, denominators and prior-expression
status), and 40,320 source-level values across all metrics. Verification checks
stratum partitions, n=0/n=1 intervals, majority membership, risk-set bounds,
reproduction of earlier unstratified contrasts, and invariance of answer-only
outcomes to fact settings. UI checks cover all 672 new control combinations.
