# Cross-round merging in the MedCase24 pilot

All calculations are offline. The five conditions share the same 24 selected cases. Effects below are paired within case. They describe the saved fact labels, not clinical truth.

## Two complementary measures

**Cross-round compression C = 1 − N(all rounds) / [N(R1) + N(R2) + N(R3)].** Each N counts output-only equivalence components. A higher C means that pooling rounds removes a larger fraction of the separately counted units. This is a normalized merging level, not a per-edge probability.

**Direct recurrence D.** For each round pair, find units with an identity or direct equivalence link to at least one unit in the other round. Average the matched fraction from both sides, then average R1/R2, R1/R3 and R2/R3. D uses within-round units but no cross-round closure. A raw-atom version uses no union-find at all.

| Setting | Compression C | Direct recurrence D | Raw atom recurrence |
|---|---:|---:|---:|
| shared-generic | 50.6% | 57.2% | 61.2% |
| shared-specialist | 50.9% | 56.1% | 59.1% |
| split-generic | 37.2% | 39.1% | 41.1% |
| split-specialist | 39.1% | 41.2% | 42.2% |
| split-mismatched | 40.8% | 41.9% | 42.4% |

## Shared minus split, paired by case

| Role configuration | Metric | Difference, pp | 95% case-bootstrap CI, pp |
|---|---|---:|---:|
| generic | compression | +13.4 | [+11.2, +15.7] |
| generic | direct_coverage | +18.1 | [+16.0, +20.5] |
| generic | raw_direct_coverage | +20.1 | [+17.6, +22.7] |
| specialist | compression | +11.8 | [+8.9, +14.8] |
| specialist | direct_coverage | +15.0 | [+11.4, +18.4] |
| specialist | raw_direct_coverage | +17.0 | [+13.2, +20.6] |

All six exploratory contrasts have two-sided case sign-flip p < .001 and BH q < .001 (100,000 draws). The uncertainty unit is 24 cases, not 120 traces or thousands of edges.

## What accounts for the compression difference?

Compression decomposes exactly into (1) repeated global-cluster round presences and (2) additional merging of within-round components through cross-round bridges. These are accounting terms under the final equivalence partition, not independent causal mechanisms.

| Setting | Repeated-presence share | Bridge share |
|---|---:|---:|
| shared-generic | 32.2% | 18.4% |
| shared-specialist | 30.6% | 20.2% |
| split-generic | 25.3% | 11.9% |
| split-specialist | 26.0% | 13.0% |
| split-mismatched | 25.5% | 15.3% |

Shared–split compression differences split almost equally between the two terms for generic agents (6.9 pp repeated presence, 6.5 pp bridges). For specialists they are 4.6 pp and 7.2 pp. Raw atom recurrence is also 17–20 pp higher under shared information, so a union-find artifact alone cannot account for the pattern.

## Persistence across rounds and thresholds

Direct recurrence grows from R1/R2 to R2/R3 in every setting. Shared generic rises from 53.9% to 66.5%, while split generic rises from 33.1% to 53.1%. Shared specialist rises from 54.5% to 64.7%, versus 36.1% to 54.2% for split specialist. Communication narrows the descriptive gap, but it remains at the final transition.

Across saved-margin thresholds 4.5, 5.0, 5.28, 5.5 and 6.0, the shared–split compression gap stays about 11.6–13.8 pp. The direct-recurrence gap stays about 14.7–18.2 pp. Blocker-negative pairs stay unrelated throughout. Threshold sensitivity does not establish the accuracy of the matching model.

## Interpretation

In this controlled pilot, information allocation changes cross-round redundancy much more than role labels change it. Within shared information, specialist−generic compression is +0.3 pp [−2.2, +2.7]. Within split information it is +1.9 pp [−0.6, +4.2]. Mismatch−matched-specialist compression is +1.7 pp [−0.5, +3.9]. These smaller contrasts do not establish a role-driven compression difference.

A supported description is: splitting initial evidence leaves more distinct content across rounds and less direct recurrence, even after normalization. A plausible mechanism is that agents start with different evidence and revise their content after receiving peers, whereas shared agents can repeatedly select the same evidence. This mechanism remains a hypothesis: C and D do not distinguish repeated evidence, independent derivation and actual copying, and the pilot has one trace per case-condition.

Use C as a single trace-level merging feature and D as its direct-match robustness companion. Lower merging is neither necessarily better nor necessarily worse: retained diversity can reflect useful complementarity, unresolved disagreement, or unsupported content. Final diagnosis labels do not supply gold truth for every atomic fact.

Reproduce: `.venv/bin/python scripts/study_report/merge_levels.py`. Full case-level values, paired differences, round pairs and threshold sensitivity are in `analysis.json`.
