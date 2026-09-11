# Early fact patterns and final diagnosis

Exploratory offline audit of 120 traces on the same 24 cases. No new model calls, extraction, or labels. The fixed primary family contains 12 metrics; targeted follow-ups are explicitly separate.

## Main findings

R2 original-evidence coverage is the strongest replication candidate. A 1-SD increase (8.9 percentage points of coverage) is associated with +11.1 pp final accepted accuracy [3.9, 18.3], after case and condition fixed effects, R1 output token volume and the fraction of R1 agents already correct. Cluster-robust p=.011; BH q=.129 across all 12 metrics. No primary metric reaches q<.05.

The direction persists after removing uncertain final labels, controlling initial coverage, and excluding diagnosis-tagged facts. However, conditioning on R2 agent correctness reduces the estimate to +1.1 pp [-2.3, 5.2] per SD. This can reflect a shared reasoning state or a pathway mediated by an improved R2 diagnosis; it does not identify which causes which.

Correct-source peer uptake advantage is +7.6 pp [3.9,11.2] within the same R1 panel. After removing all source units bearing a diagnosis tag, it is -0.3 pp [-4.9,3.9]. The paired change is +8.0 pp [5.2,10.7]. Diagnosis tags cover judgments and medical reasoning, not just the final-answer string. They affect 49.4% of R1 within-output units on average. This is a substantial compositional ablation, not proof that agents merely copy answers.

Adding all 12 facts metrics does not improve held-out-case Brier score in the fixed ridge-logistic baseline. The audit therefore has candidate explanatory associations, not a validated failure detector.

## Definitions and statistical model

- Primary outcome: accepted R3 semantic-system diagnosis (S or L). The 120 traces contain S=55, L=29, D=22, U=14. U counts as not accepted in the main analysis, not as definitely wrong. Excluding U is a sensitivity analysis.
- Predictors use only R1, R2 and R1→R2 flow. No R3 output facts enter them. Only 13 of 24 cases vary in accepted final outcome across the five settings.
- Original-evidence coverage: fraction of equivalence units in original source cards with an identity/direct-equivalence match in the union of the three agents’ outputs for that round. Metadata is excluded. This is case-evidence coverage, not coverage of clinically necessary clues.
- Novel share: fraction of R2 output units without an identity/direct-equivalence match in any R1 output.
- Domain entropy: fractional domain mass over eight categories, divided by log2(8). Professional uptake prime uses the existing fractional scheme.
- Each primary feature enters a separate linear probability model standardized by its overall sample SD. Controls: case and condition fixed effects, log R1 visible-output tokens, R1 accepted agent fraction. The latter uses gold labels, so this is an explanatory adjustment, not a deployable predictor.
- CIs: 2,000 case-bootstrap resamples. p: case-cluster sandwich covariance with finite-sample correction and t distribution, G−1 degrees of freedom. q: BH across the fixed 12 primary coefficients. Bootstrap CI and cluster-t p can disagree near zero because they are different small-sample approximations.
- Controls are not causal identification: R1 correctness may mediate R1 fact effects, while R2 correctness can mediate or confound later associations. Conditioning on final success to explain uptake can also create selection effects.

## Full primary family

| Metric | Accuracy difference per 1 SD, pp | 95% case-bootstrap CI | Cluster p | BH q |
|---|---:|---:|---:|---:|
| R1 fact density | -2.8 | [-16.7, +8.9] | 0.701 | 0.935 |
| R1 evidence coverage | +2.0 | [-6.5, +10.7] | 0.688 | 0.935 |
| R1 domain entropy | -8.5 | [-15.6, +0.2] | 0.073 | 0.292 |
| R1 peer overlap | -0.7 | [-14.5, +17.7] | 0.941 | 0.941 |
| R2 evidence coverage | +11.1 | [+3.9, +18.3] | 0.011 | 0.129 |
| R2 domain entropy | -7.3 | [-21.7, +8.2] | 0.414 | 0.829 |
| R2 novel fact share | +9.3 | [-2.2, +21.8] | 0.194 | 0.465 |
| R2 professional uptake prime | -0.8 | [-9.8, +8.6] | 0.873 | 0.941 |
| R1→R2 peer uptake | -4.2 | [-20.2, +14.5] | 0.687 | 0.935 |
| R1→R2 new-to-peer uptake | -1.7 | [-12.0, +9.2] | 0.792 | 0.941 |
| R1→R2 self retention | -6.7 | [-14.6, +3.1] | 0.172 | 0.465 |
| R1–R2 compression | -11.2 | [-22.2, -2.5] | 0.058 | 0.292 |

R1 entropy has a negative tendency (-8.5 pp [-15.6,+0.2], q=.292), but is sensitive to grading/adjustment and may reflect diagnosis-label concentration. Compression and novelty are less robust: their associations weaken markedly when uncertain diagnoses are excluded. Increasing n will not automatically remove these biases or guarantee significance.

## Coverage robustness, common effect scale

All rows below report accuracy difference for +10 percentage points of coverage.

| Analysis | Difference, pp | 95% CI, pp |
|---|---:|---:|
| Primary | +12.5 | [+4.4, +20.6] |
| exclude_U | +7.6 | [+1.8, +14.7] |
| same_only | +8.8 | [-0.3, +19.2] |
| adjust_R2_correctness | +1.3 | [-2.6, +5.9] |
| Control R1 coverage | +12.9 | [+5.0, +21.4] |
| Exclude diagnosis tags | +13.6 | [+5.7, +21.6] |

Targeted checks above were added after reading the initial results. They are sensitivity analyses, not independent confirmations. The R2 coverage coefficient stays positive when each of the 24 cases is omitted in turn.

## Why a source might receive more uptake

Only R1→R2 peer edges are used, without stratifying by final outcome. Both source and recipient R1 diagnoses must have S/L/D labels (472 edges, 24 cases). The within-panel model uses case×condition fixed effects. The adjusted model additionally controls recipient correctness, prior same diagnosis, pre-existing fact overlap and log source fact count. Source units have equal contribution to an edge rate; edges enter the model equally, inference clusters by case.

| Measure | Adjustment | Correct-source advantage, pp | 95% CI |
|---|---|---:|---:|
| rate | within_panel | +7.6 | [+3.9, +11.2] |
| rate | prior_state_adjusted | +5.4 | [-2.1, +12.0] |
| new_rate | within_panel | +7.7 | [+3.6, +11.6] |
| new_rate | prior_state_adjusted | +4.7 | [-3.4, +11.9] |
| nodiag_rate | within_panel | -0.3 | [-4.9, +3.9] |
| nodiag_rate | prior_state_adjusted | -2.1 | [-11.1, +5.3] |
| new_nodiag_rate | within_panel | +0.5 | [-4.2, +4.8] |
| new_nodiag_rate | prior_state_adjusted | -4.9 | [-15.0, +3.2] |

After adjustment, +10 pp of source facts already present in the recipient’s R1 output predicts +2.8 pp uptake [1.0,4.4]. The adjusted source-correctness contrast is +5.4 pp [-2.1,12.0], and same-prior-diagnosis contrast is +2.9 pp [-4.1,9.9]. Familiarity is an observable antecedent, but the result is not randomized. Prior overlap and later uptake share source-fact denominators, and semantic matching errors may affect both.

## Held-out-case prediction

Leave one entire case out, holding all five settings together. Standardization and median imputation are fitted inside each training fold. Fixed logistic L2 C=1, no hyperparameter search. Observable baseline: setting, R1 log tokens, R1 pairwise answer agreement. Oracle baseline adds R1 accepted agent fraction. Fact models add all 12 prespecified metrics.

| Model | Brier (lower better) | AUROC | Log loss |
|---|---:|---:|---:|
| observable_baseline | 0.224 | 0.465 | 0.651 |
| observable_facts | 0.239 | 0.546 | 0.699 |
| oracle_baseline | 0.107 | 0.872 | 0.374 |
| oracle_facts | 0.125 | 0.874 | 0.405 |

Brier improvement (baseline minus fact model):
- observable: -0.015 [-0.056,+0.018].
- oracle: -0.018 [-0.034,-0.003].

These intervals bootstrap the 24 held-out case losses; training-set uncertainty is not included. A negative Brier improvement means worse prediction. No claim that every possible fact-based model will fail; this fixed model lacks demonstrated incremental generalization.

## Causal next step

Freeze R1 outputs, then randomize which original-evidence facts appear in R2 peer messages while matching message length, source identity and diagnosis wording. Separately vary whether a fact is already familiar to the recipient. Measure R2 evidence recovery and blinded R3 diagnosis. This intervenes on evidence exposure before the outcome and tests whether recovered evidence causes a correction. Diagnosis wording can be held fixed or randomized as its own factor to distinguish evidence uptake from conclusion alignment. No such intervention has been run here.

The pilot still lacks clinician-reviewed fact truth/relevance, independent repeated seeds, and enough independent cases for stable high-dimensional prediction. Case selection, one trace per condition, uncertainty in diagnosis grading, and imperfect matching remain material limitations. Neither temporal order nor a larger observational sample alone identifies the causal path.

Reproduce: `.venv/bin/python scripts/study_report/fact_outcome.py`, then `scripts/study_report/fact_outcome_followup.py`, then `scripts/study_report/report_fact_outcome.py`. Source observations, all regression points and prediction probabilities are retained under `findings/medcase24-fact-outcome/`.
