# MedCase24 figure exports

Run `.venv/bin/python scripts/study_report/export_figures.py` after the completed
study analysis. Install optional `report` dependencies if needed. Verify with
`.venv/bin/python scripts/study_report/check_figures.py`.

Outputs live under ignored `findings/medcase24-figures/`. All chart labels are
English. Charts, heatmap cells and colorbars are vector objects with embedded fonts.
No model calls, matching changes or label changes are made.

## Contents

| PDF | Pages | Content |
|---|---:|---|
| 00_all_figures.pdf | 27 | Combined collection, ordered as below |
| 01_uptake_prime.pdf | 1 | R1/R2/R3, five condition rows, labels only on the left |
| 02_output_preference.pdf | 2 | Same layout: own-profession output share, then output prime |
| 03_facts_by_output_tokens.pdf | 4 | All rounds cumulatively, then each round separately |
| 04_source_uptake_heatmaps.pdf | 2 | R1→R2 / R2→R3, five settings and equal setting mean |
| 05_correctness_and_final_outcome.pdf | 4 | Each transition: paired panels, then all classified sources |
| 06_majority_advantage.pdf | 2 | Each transition, 2:1 panels, self/peer rates |
| 07_correctness_by_majority.pdf | 12 | Each transition for all settings and each setting separately |

Twelve additional single-figure PDFs export the individual source heatmaps and
mean heatmaps separately. `figure-data.json` contains the numerical points and
summaries; `token-clock.json` contains occurrence events and prefix trajectories;
`audit.json` and `verification.json` describe provenance and checks.

## Fixed metric choices

The principal figures retain the already established baseline: within-set
equivalence components, direct equivalence uptake, fractional original-domain
labels, saved NLI threshold 5.28. This baseline gives a clear specialist uptake
prime result and avoids changing definitions between related panels. No condition,
role, case or round gets its own tuned threshold. Source-rate figures are unweighted
rates over all source-output units; they have no multi-label weighting operation.

The output-preference PDF leads with own-profession share, which has the clearer
reported effect, and also provides output prime (own share minus other share) in
exactly the same visual layout. Profile points are per-case/agent ratios, with
profession-specific means and a case-mean overall mean. Undefined prime is omitted
rather than zero-filled. Source roles use actual mismatched prompts, information
roles for split/generic, and case-aligned virtual roles for shared/generic.

## Token clock and distinct-fact curves

The fixed tokenizer is `BAAI/bge-base-en-v1.5`, matching the old project's token
clock. It is loaded locally without model inference. Output texts are tokenized
without special tokens, truncation or padding. Browser UTF-16 span offsets are
converted back to Python character positions. A fact appears when the end of its
first supporting span has been reached. This intentionally uses **quote end**,
whereas the old clock recorded quote start; both are proxy positions. Token offsets
from the full output encoding determine prefix lengths without repeatedly tokenizing
substrings. Missing spans use the turn end and are explicitly flagged.

- 36,192 / 36,664 output fact mentions locate directly (98.71%).
- 472 mentions (1.29%) use the end-of-turn fallback.
- The clock counts visible output text only, not billed tokens, hidden reasoning,
  inputs, network time or elapsed time. Synchronous turns are ordered round then
  A/B/C solely for accounting. Seat order is not a causal transmission order.
- The cumulative curve counts components in the graph of output atoms encountered
  **so far**. An arriving node can bridge earlier components, so the count can
  decrease. No future nodes provide bridges. Round-only curves reset both tokens
  and fact graph at the start of the chosen round.
- All 480 trace/round endpoint counts reproduce the original report's equivalence
  totals exactly. The 24-case means use a common absolute-token range ending at the
  shortest trace in that panel, so all means use the same 24 cases per setting.
  Complete individual trajectories show the remaining ranges without extrapolating
  stopped traces or silently changing the sample composition.

## Heatmaps

Source-uptake prime maps use source profession on rows and recipient profession on
columns. Own/other categories are relative to the recipient. Diagonal cells are
self retention. Compute each case's prime first, then average; missing professional
denominators remain NA. The overall grid is the arithmetic mean of the five setting
cell means, not a ratio of pooled fact counts. Both transitions use the same
symmetric color scale. Individual single-heatmap PDFs use that same scale.

Correctness × majority grids instead show mean unweighted source uptake rates,
with correct S+L / incorrect D rows and majority / minority columns. Self and peer
rates are separate panels. They include all eligible sources per cell, so different
cells may use different cases. They are descriptive cell means, not matched causal
contrasts. Correct-minority cells DO have observations (3 cases at R1, 2 at R2 in
the pooled view); the missing design cell from earlier analysis was the **joint
panel condition** correct minority versus two D majority agents. Do not conflate
the marginal source cell with that stronger conflict criterion. NA and n=1/n<5
cells retain explicit sparse-data markings.

## Source scatter plots and confidence intervals

Every plotted point is one source-recipient edge. A self source contributes one
edge; a peer source contributes two. Role color follows the source. Shapes encode
S+L versus D, or majority versus minority. Columns show all final outcomes, final
S+L, and final D; the first column overlaps the other columns by design and can
include final-U traces. The two main rows are self retention and peer uptake.
Separate summary strips beneath the dots show source-group means and intervals.

The primary correctness pages restrict to case/condition/round panels containing
both source groups, reproducing the earlier within-panel reversal comparison.
Companion pages plot all classified source edges and their descriptive means;
those groups need not share cases. Majority pages use all strict 2:1 panels.
Unanimous, three-way disagreement and nontransitive synonym triples are excluded.

Means first average recipient edges within source, then sources within each
case-condition panel, then panels within case, then cases. Thus a large number of
edges does not masquerade as independent cases. Dark intervals are the 2,000-draw
case bootstrap; thin gray intervals are Student-t sensitivity based on case means,
clipped to 0–100% for the rate axis. Intervals are unavailable at n<2. Point data and
unclipped interval values remain in JSON. Final-error sparse panels do not establish
subjective cognition, and correctness of a diagnosis does not certify each fact.

## Verification and HTML

Numerical checks reproduce prior role means, the within-panel correctness and
majority contrasts, all token-curve endpoints, and equal-setting heatmap means.
The 20 PDFs have 27 master pages, with no embedded raster images or text outside
page bounds. Master pages were rendered and visually checked. The HTML report's
scatter labels now occur only on the left; its directed source diagrams are replaced
with interactive prime heatmaps. It links all figure families and the ZIP bundle.
The existing report control tests were updated for heatmap cells and still pass.
