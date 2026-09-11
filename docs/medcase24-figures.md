# MedCase24 figure exports

Generate with `.venv/bin/python scripts/study_report/export_figures.py`; verify and
package with `.venv/bin/python scripts/study_report/check_figures.py`.
Install the optional `report` dependencies first. The exporter reruns the offline
revision audit automatically. It makes no API calls and changes no saved labels.

## PDF contents

| PDF | Pages | Content |
|---|---:|---|
| 00_all_figures.pdf | 19 | Combined collection |
| 01_uptake_prime.pdf | 1 | R1–R3, paired setting backgrounds and profession-mean connectors |
| 02_output_preference.pdf | 2 | All output facts: own share, then own minus other share |
| 03_facts_by_output_tokens.pdf | 1 | Cumulative left; R1/R2/R3 and within-case round mean in a right 2×2 grid |
| 04_source_uptake_heatmaps.pdf | 2 | Five settings + equal setting mean per transition |
| 05_correctness_and_final_outcome.pdf | 2 | Pooled transitions: scatter, then boxplot |
| 06_majority_advantage.pdf | 2 | Pooled transitions: scatter, then boxplot |
| 07_correctness_by_majority.pdf | 2 | Six 2×2 grids per page; self retention, then peer uptake |
| 08_new_fact_preference.pdf | 4 | New-output own share/prime, novelty beyond initial evidence, new-vs-old interaction |
| 09_paired_role_contrasts.pdf | 3 | Specialist − generic within case, separately for shared/split information |

The master groups all preference figures first: 01, 02, 08, 09, followed by 03–07.
New-output preference starts on master page 4. The former three separate round-only
token pages are removed. Twelve additional PDFs contain individual 3×3 source heatmaps. All plots are
English vector graphics with embedded fonts. The ZIP includes PDFs, numerical
points, cached token clocks, audit data, methods and the four figure scripts;
rebuilding also requires the analysis modules and saved study data in the project.

## Fixed definitions

The baseline remains within-set equivalence components, direct equivalence uptake,
fractional original-domain labels, and saved NLI threshold 5.28. No per-setting
threshold tuning or significance-based metric selection is used. Source-uptake
rates are unweighted fractions of source-output units. Profession colors follow
actual prompts for mismatched experts, information assignments for split/generic,
and case-aligned virtual roles for shared/generic.

The first three profile pages use **all output facts**, including repeats and
restatements of received information. Own share divides fractional own-domain
mass by output fact units. Output prime subtracts other-domain share. Clinical is
history/examination, lab is laboratory/pathology, and imaging is imaging.
Diagnosis/treatment/other are shared categories: they count in output denominators
but neither own nor other numerators. Uptake prime instead subtracts two uptake
rates with separate own/other source denominators. Undefined ratios stay missing.

Generic and specialist conditions are visually paired using background bands and
profession-mean connectors. Other adjacent condition rows have dashed connectors;
the same connections include black overall means. Every profile row prints the
black case-mean value at right (percent for shares, percentage points for primes).
Summary markers distinguish generic (circle), specialist
(diamond) and mismatch (triangle). The supplementary paired-effect pages subtract
generic from specialist within the same case and information allocation; zero is
therefore the direct role-effect reference, unlike the raw profile levels.

## Novel output facts

A current output equivalence unit is new when none of its members has identity or
a direct saved equivalence link to any agent's output in an earlier round. Other
agents' simultaneous outputs are not prior information. R1 is all new under this
output-history definition. A second sensitivity view also excludes matches to
initial evidence. New + old exactly partitions each current output's units.
These are first-expression proxies under the saved matching, not proof of newly
created knowledge or of correct inference. No future bridge defines novelty.

The new-vs-old interaction subtracts the specialist−generic effect among old units
from the same effect among new units, paired by case. It does not infer an
interaction by comparing two separate confidence intervals. Ratios with no units
are omitted. All four own-share interactions (shared/split × R2/R3) include zero;
the data do not establish a stronger role effect on novel facts.

## Token clock and cross-round deduplication

The locally cached `BAAI/bge-base-en-v1.5` tokenizer estimates visible output tokens,
without special tokens, truncation, padding or hidden reasoning. UTF-16 quote spans
are converted to Python character positions. Facts enter at the end of their first
supporting span; the old project used quote start. 36,192/36,664 mentions locate
(98.71%); the remaining 472 use end of turn and are flagged. Parallel turns are
ordered by round, then A/B/C solely for accounting, not causal transmission.

Each curve counts components among output atoms seen **so far**. Later nodes may
bridge components, allowing decreases. Round-only curves reset the graph. All 480
endpoints reproduce saved fact totals. The cumulative mean curve shares the minimum complete token budget across all
120 traces. The four right panels share the minimum within-round token budget
across 120 traces × 3 rounds. The mean-round panel first takes the arithmetic mean
of a case's R1/R2/R3 curves at the same within-round token position, then averages
cases, bootstrapping cases jointly across rounds. It never merges facts across
rounds. No individual trajectories are plotted and there is no extrapolation.

For each trace the audit exactly decomposes:

`sum of separate round components − complete trace components = repeated cluster-round presences + cross-round bridge reduction`.

Here cluster-round presence uses the final output-only component partition for a
**post-hoc accounting identity**, not for the online clock or novelty. The bridge
term counts extra within-round components that merge when all rounds are included.
Thus stronger cumulative compression is not entirely simple repeated wording.

| Setting | Sum of round counts | Trace count | Repeat excess | Bridge reduction |
|---|---:|---:|---:|---:|
| Shared / generic | 197.00 | 97.46 | 63.33 | 36.21 |
| Shared / specialist | 214.71 | 105.88 | 65.58 | 43.25 |
| Split / generic | 211.29 | 132.75 | 53.38 | 25.17 |
| Split / specialist | 224.21 | 136.58 | 58.33 | 29.29 |
| Split / mismatched | 226.12 | 133.58 | 57.67 | 34.88 |

Shared conditions lose about 51% of separate-round counts after pooling, versus
37–39% for matched split conditions (mean per-trace compression). Both greater
cross-round recurrence and more bridging contribute to the cumulative gap.

## Pooled source scatter, boxplots and inference

R1→R2 and R2→R3 are pooled. Green/red denotes the R3 **system** outcome (correct /
incorrect). Circle/triangle denotes the **source agent's** diagnosis at the round
whose facts are offered for uptake (correct / incorrect). Correct = S+L, incorrect
= D. Unclassified source or final outcomes are excluded from these colored plots.
Majority comparisons use strict 2:1 panels, with majority/minority shown as two
bands or two boxplot groups; shapes still denote source correctness in scatter.

Scatter summary rows are ordered by final outcome: correct-source / incorrect-source
within final-correct first, then the same groups within final-incorrect. Green/red
bands mark those two final-outcome groups. Majority pages follow the same ordering.

Boxplots use a 2×3 layout: self retention / peer uptake on rows, and all classified
finals / final correct / final incorrect on columns. The all-finals column shows
both colored strata side by side; the right columns repeat the individual strata
and retain the existing paired tests. It introduces no new significance tests.

Dots are source-recipient edges. Summary statistics first average recipients
within source, sources within case-condition-round groups, rounds within condition,
conditions within case, and finally cases. Boxplots show the resulting **case means**,
not thousands of dependent edges. Median, IQR and 1.5-IQR whiskers are accompanied
by mean diamonds, 95% case-bootstrap intervals and case counts. Sparse final-error
cells remain visibly sparse.

Descriptive boxes can contain different cases. Inferential differences separately
restrict to panels containing both source groups, compute the within-panel gap,
average rounds/conditions within case, and estimate the mean case gap. Plot n for
these tests can therefore differ from box n. Δ is correct−incorrect or
minority−majority. All tests are two-sided case sign flips (exact up to 16 cases,
100,000 draws above that), assuming symmetric case effects under the null. The
predefined eight contrasts (two questions × self/peer × final correct/incorrect)
receive BH-adjusted q values. Exact p/q are shown rather than stars; <.001 never
prints as .000. Missing inference at fewer than two cases is not zero significance.

The JSON additionally retains Student-t sensitivity intervals. For failed-final
peer uptake the bootstrap interval is negative but there are only three paired
cases: the t interval crosses zero and sign-flip p=.25, q=.40. This does not establish
a reliable reversal or a mechanism of subjective correctness. These figures show
associations, not causal effects of making a diagnosis correct.

## Heatmaps

The 3×3 source-prime maps retain separate transitions. Rows are source professions,
columns recipient professions; own/other are relative to the recipient. Diagonal
cells are self retention. Overall means give each setting mean equal weight.

The 2×2 correctness × majority maps pool both transitions, with five settings and
an overall map on each page: self retention first, peer uptake second. They include
all sources with known correctness in strict 2:1 panels, including traces with an
unclassified final outcome because final outcome is not a grouping variable here.
Cells show mean, independent case n and a 95% case-bootstrap interval. Empty cells
remain NA. The overall cell is the equal mean of **available** setting-cell means;
its k/5 coverage is explicit. Overall intervals jointly resample the same case IDs
across settings, preserving repeated-case dependence. Correct minority is an
observed marginal cell; it is not equivalent to a correct minority opposed by two
incorrect majority agents.

## Clinical pattern audit

The clinical prompt explicitly specializes in history, symptoms, bedside
examination and temporal course. The data cannot attribute a difference to an
underspecified generalist prompt. The role's label taxonomy is also broader than
imaging, and diagnosis is shared rather than credited to clinical.

R1 split clinical prime is defined in only 14/24 cases; the other-profession input
mass has median 1, compared with about 24 for own mass. This makes R1 comparisons
unstable. Restricting both denominators to at least 3 leaves only 7 cases and does
**not** eliminate the negative specialist clinical prime; denominator imbalance
therefore does not fully explain it. Later rounds have all 24 denominators defined.

The alleged opposite trajectory is not universal: in split/specialist output,
clinical, lab and imaging own shares all decline from R1 to R3. More decisively,
R3 specialist−generic uptake-prime differences are positive for all three roles
in both shared and split settings. Clinical can have a negative raw prime while
still showing a positive role effect. The paired-effect PDF makes this distinction
visible without changing metric definitions.

## Verification

Checks reproduce original profile means, 480 token endpoints, pooled source case
means and within-panel inference, equal-setting map means, the repetition accounting
identity, and exhaustive new/old partitions. PDFs are checked for text outside page
bounds and embedded raster images, rendered for visual inspection, and packaged
with checksums. `revision-analysis.json` retains the full exploratory audits and
paired effects. No additional model calls or billing occurred.
