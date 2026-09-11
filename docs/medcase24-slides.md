# MedCase24 mentor slides

The English 18-slide deck is generated locally at
`findings/medcase24-slides/clinical-factflow-mentor-v4.pptx`.
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
the source JSON. All 18 final slides were rendered for visual review. Native
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
8%-opacity clinical/lab/imaging frames, using rendered line breaks and Arial font
advances. Frames remain separate editable shapes. Slide 6 uses circular nodes and
curved directed paths, with arrow tips outside the node boundary. Slide 7 adds the
saved pointwise 95% case-bootstrap intervals (2,000 resamples, 24 cases). Its CI
bands are editable polygons behind transparent native charts. Update the bands
when changing chart data or geometry; they are not linked Excel error bands.
