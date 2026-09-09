# Pitfall audit carried into the new project

Read sources in the old workspace: root README.md, AGENTS.md, findings/README.md,
all eight defects in fix.md, extraction/atomization/blocking and matching code,
experiments/matcher_eval/README.md, and discipline annotation operating notes.
No historical numerical conclusion is imported as a new result.

| Recorded problem | New handling | What still needs empirical validation |
|---|---|---|
| fix #1: omitted noun phrases were not resolved | Resolve within the target text only; missing referents remain ambiguous. Full visible-input context was removed after the MiniMax audit found leakage | Human checks of extracted references; prompt wording is not a guarantee |
| fix #2: inconsistent conjunction splitting and narrow prefilter | User-requested candidate-only pass (2026-09-09): broader list/quantifier/reference/quote screening; worked split / no-split examples; exact selected-parent coverage. Original all-parent mode remains explicit | Clinical granularity, screening false negatives and conjunction error rate; see candidate speed audit |
| fix #3: subset siblings inflate apparent novelty | Preserve scope, uncertainty, time, values, units; dedupe within a record without discarding occurrences | New-corpus subset audit, not subtraction of an old 9.6% bias estimate |
| fix #4: matching threshold cannot fix bad atoms | Inherited cutoff explicitly labeled unvalidated for this domain; no threshold loosening | Independent domain-specific gold for both blocker and NLI |
| fix #5: source rereading confounded with peer transmission | Source allocation and first/every-round visibility are explicit; actual source / peer / self IDs recorded per turn | A visible matching fact remains an opportunity, not proof of causal use |
| fix #6: overlapping spans dropped atoms | All atom children and all quote positions retained, unlocated spans explicit | Span accuracy and repeated-quote ambiguity |
| fix #7: no self memory was called retention | `none/last/all` self memory is independent of peer memory; messages saved verbatim | Interpretation of recurrence under each declared memory setting |
| fix #8: synchronous chain needs multiple rounds | Separate synchronous and sequential schedule; regression tests for first-round and final-round visibility | Compare like schedules; rotate node position |
| Cached generalists were copies of one draw | No generation cache; independent calls; per-agent/round/replicate seed streams if configured | Sampling diversity is not guaranteed by a temperature alone |
| Fixed temporary filename caused concurrent write races | Unique temporary files followed by atomic replacement; run IDs prevent collisions | Filesystem / storage reliability on target host |
| Silent dropped calls and empty extraction | Bounded retries; empty extraction is a failed attempt; failed run/stage never marked complete; all HTTP attempts audited | Empty input may genuinely be non-propositional; review before designing an exemption |
| Invalid batch items were guessed or lost | Strict schema, exact parent-ID coverage, missing scores fail | Taxonomy reliability and disagreement with experts |
| Annotation inherited wrong polarity after splitting | Each child receives fresh full annotations; parents remain inspectable | Negation and modality accuracy |
| Prompt / batch changes made mixed corpora incomparable | Full YAML, code hash, schema, data hashes and artifacts verified; existing stage directories never overwritten | Provider model drift despite identical model name; resolved response identity recorded when available |
| Qwen thinking contaminated first-token YES/NO scores | `enable_thinking=False`, exact legacy entailment prompt, bidirectional margins, token IDs recorded | Validate tokenizer template and scoring on intended checkpoint/runtime |
| CUDA wrong card, missing kernels, hardcoded scratch | Optional read-only GPU check; no hardcoded server/GPU, eager attention, local cache preference | Install correct torch/CUDA build on target GPU server |
| False equivalence amplified by union-find | Complete-link clusters, every intra-cluster pair has explicit equivalence | Conservative under-merging; inspect direct edges as well as clusters |
| Per-mention edges inflated semantic counts | Separate text nodes, mentions, direct pair relations and actual delivery records | Future analyses must state units and denominators |
| Summary duplicated reports; imaging answers leaked | Explicit summary cutoff; default excludes impressions; imaging task rejects its own gold as input | Audit source JSON schema and summaries on approved corpus |
| Benchmarks saturated, tiny samples misled | Fixture and pilot clearly marked; no research claim from smoke runs; design includes solo/shared controls | Adequate cohort, task difficulty and outcome reliability |
| Catalogue prices confused with actual bills | Preserve usage and missing usage per attempt; no hardcoded dollar rates | Get current rates or subscription quota rules when actually costing an experiment |

The core regression suite exercises these failure modes with synthetic data and
fake model responses. It proves that the pipeline records and validates the stated
conditions; it does not prove the model follows the prompts or that a medical claim is true.
