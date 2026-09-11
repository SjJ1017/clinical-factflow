# Direct fact-to-outcome audit (exploratory)

Freeze before testing associations: 12 primary trace metrics available by R2, no R3 facts.
R1: fact density, original-evidence coverage, domain entropy, peer overlap.
R2: original-evidence coverage, domain entropy, novel-to-prior-output share, professional uptake prime.
R1→R2: peer uptake, new-to-peer uptake, self retention, cross-round compression.
Use equivalence units, direct matches, fractional domain labels. Main outcome is
R3 accepted diagnosis (S/L); U is not accepted but must not be called definitely
wrong. Sensitivity excludes U, and stricter S-only outcome is also retained.
Fit each feature separately with case and condition fixed effects, log R1 output
tokens and initial R1 agent correctness fraction. Compare weaker adjustment to
expose confounding/overadjustment. Cluster inference by 24 cases; BH over the 12
primary adjusted coefficients. No claims of causality or future significance.

Additional targeted checks: (1) no-diagnosis-tagged-fact sensitivity; (2) direct
source correctness versus uptake, controlling recipient's prior answer and prior
fact overlap, only R1→R2 peer edges, without stratifying on final outcome; (3)
leave-one-case-out prediction with fixed ridge logistic settings, all prespecified
features, and complete case holdout. Compare observable baseline and an oracle
baseline with R1 correctness. Prediction uncertainty resamples held-out case
predictions; does not include training uncertainty. Separate explanations,
prognostic associations and actual interventions.
