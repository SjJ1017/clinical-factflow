# MedCase24 mentor slides

The English 26-slide deck is generated locally at
`findings/medcase24-slides/clinical-factflow-mentor-v8.pptx`.
It covers ClinicalBench's public example, the actual MedCaseReasoning case and
partitions, controlled conditions, extraction/matching, trace links, aggregate
flow, and selected results. ClinicalBench is not presented as the pilot corpus.

All text, points, uncertainty bars, heatmap cells, arrows and diagrams are native
editable PowerPoint elements. Four charts have embedded data workbooks; other
scientific plots are rebuilt as editable vector shapes from the same numerical
results used for the PDFs. They are not screenshots. Bar-value labels are native
text overlays, so update those labels too when editing the underlying chart data.
Sources and full metric definitions are in slide notes and the accompanying reports.

## Reproduce

Use the project Python environment and the Codex Artifact Tool JavaScript runtime.
Run from the repository root, with the saved study/figure files and pilot cases
available locally. There are no API calls.

```bash
.venv/bin/python scripts/study_report/merge_levels.py
.venv/bin/python scripts/study_report/prepare_slides.py
.venv/bin/python scripts/study_report/fact_outcome.py
.venv/bin/python scripts/study_report/fact_outcome_followup.py
.venv/bin/python scripts/study_report/report_fact_outcome.py
cp scripts/study_report/build_slides.mjs findings/medcase24-slides/build/build.mjs
ln -s "$RUNTIME_NODE_MODULES" findings/medcase24-slides/build/node_modules
"$RUNTIME_NODE" findings/medcase24-slides/build/build.mjs
```

The symlink is only needed once. `RUNTIME_NODE_MODULES`, `RUNTIME_NODE`,
`RUNTIME_PYTHON`, and `PRESENTATIONS_SKILL_DIR` should identify the installed Codex
runtime and presentation skill. `FACTFLOW_ROOT` can override the project root.
Set `FINAL_PPTX` to a new absolute filename when regenerating: the finalizer
intentionally refuses to overwrite a validated deliverable. Intermediate outputs,
local evidence and the PPTX are ignored by Git.

The finalizer verifies package integrity, font policy, layout geometry, editable
table and chart presence, and chart/workbook agreement. Numerical chart cells are
rounded to 10 decimal places for Excel serialization; full precision remains in
the source JSON. All 25 final slides were rendered for visual review. Native
PowerPoint application opening is not part of this validation.

## Sources

- ClinicalBench public example: https://github.com/WeixiangYAN/ClinicalLab
- Selected public record: https://github.com/WeixiangYAN/ClinicalLab/blob/main/data_examples/data_example_en.json
- Actual dataset: https://huggingface.co/datasets/zou-lab/MedCaseReasoning
- Pilot case: `mcr-train-PMC3420544`, frozen revision `469a536`, train row 423.
- Study results: `findings/medcase24-study/summary.json` and social uptake observations.
- Figure results: `findings/medcase24-figures/figure-data.json`.
- Merging audit: [medcase24-merging.md](medcase24-merging.md).

The selected trace links are verified against both saved direct-equivalence scores
and receiving-card visibility. Graph arrows represent possible transmission, not
proof of copying. Case-paired inference uses 24 independent cases, never 120 traces
or individual edges as independent patients.

## Annotated slide refinements

Slide 2 preserves the full original paragraph and marks source-partition spans with
14%-opacity clinical/lab/imaging frames, using rendered line breaks and Arial font
advances. Frames remain separate editable shapes. Slide 6 uses circular nodes and
curved directed paths, with arrow tips outside the node boundary. Slide 7 adds the
saved pointwise 95% case-bootstrap intervals (2,000 resamples, 24 cases). Its CI
bands are editable polygons behind transparent native charts. Update the bands
when changing chart data or geometry; they are not linked Excel error bands.

## Direct fact-to-outcome audit (slides 19–25)

The additional seven pages cover temporal scope, all 12 primary associations,
original-evidence coverage sensitivity, diagnosis-content ablation of uptake,
prior fact overlap, held-out-case prediction, and replication/causal limitations.
All predictors stop at R2. There are 24 independent cases and only 13 cases whose
final accepted outcome varies across settings. None of the 12 primary coefficients
passes BH q < .05. Pointwise CIs use case bootstrap; p and q use case-cluster t
inference, so their boundaries can differ in this small sample.

R2 original-evidence coverage is the strongest replication candidate. Its link to
final accuracy attenuates after controlling contemporaneous R2 correctness, which
cannot distinguish a mediated pathway from a common latent reasoning state.
Removing diagnosis-tagged units removes the observed correct-source uptake
advantage; those tags include reasoning, not just final answers. The fixed
leave-one-case-out model has no incremental Brier improvement from fact metrics.
Full results and methods: [medcase24-fact-outcome.md](medcase24-fact-outcome.md).

`outcome_slides.mjs` reads the audit JSON and draws editable vector charts. The
final v6 package was rendered after finalization: all 25 pages rendered, modified
page 2 and new pages 19–25 visually checked, and the other 17 pages matched v4
pixel-for-pixel. Structural checks found no warnings; all slides contain native
text/shapes, with no raster picture objects. Statistical checks independently
reproduced the coverage coefficient with full dummy-variable OLS and verified
held-out Brier arithmetic. These checks do not establish causal validity.


## Five-condition diagram (v8)

A new page 5 follows the experimental-setting table. The top row shows two Shared
conditions; the bottom row shows three Split conditions on a separate background.
Large circles encode role prompts (gray/black generic, profession colors for
specialists); darker satellite dots encode initial evidence partitions. Shared
satellites form three-color triangles; Split has one colored dot per agent.
The mismatched example gives each specialist another profession's partition.
Positions illustrate the design, not the actual counterbalanced seat assignment.
Each graph has six curved directed peer arrows with tips outside node boundaries.

The deck now has 26 pages. Subsequent page numbers shift by one, so the outcome
audit occupies pages 20–26 and native charts reside on pages 8, 13 and 14.
The finalized v8 deck was rendered and checked: all 25 previous slides are
pixel-identical to v6; the added page contains native editable shapes and text.
