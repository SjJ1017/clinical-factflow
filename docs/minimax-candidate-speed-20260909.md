# Candidate-only extraction and speed audit — 2026-09-09

The same ten prespecified texts were retested with output-only extraction, candidate-only atomization and six workers. All ten completed in **177.93 seconds**. This establishes a usable small-batch turnaround, but does not establish one-hour throughput for the full corpus. A separate two-text MiniMax M3 test finished in 20.56 seconds with thinking disabled; quality still needs improvement.

## Protocol and reproducibility

- M2.5: `configs/extraction/minimax-candidates-v3.yaml`, Go API 2, Anthropic format, temperature 0, max output 8,000, timeout 120 seconds, three attempts, six workers.
- M3 alternative: `configs/extraction/minimax-m3-speed-v4.yaml`; identical prompts, fields and candidate selector, changing only model and explicit `thinking: {type: disabled}`. Two preselected outputs, S03 and S04, ran concurrently. M2.5 remains the default.
- Private artifacts: `runs/minimax-candidate-pilot-20260909/` and `runs/minimax-m3-speed-pilot-20260909/`. Each has its exact sample, config, source snapshot, execution script, generation-parent hashes, per-attempt calls, request timeline, results, pricing snapshot and audit. Archived scripts are evidence, not resumable commands: they intentionally refuse to overwrite their output directory.
- Earlier v1 artifacts and all 120 generation traces remain unchanged. No whole-corpus extraction, matching or diagnostic judging was started.

The ten texts comprise **five full agent outputs (875 words), four short source segments (110 words), and one shared-metadata text (10 words)**. The sample was not selected after observing this retest. It is too small for a model-wide error rate or a stable timeout estimate.

## What changed

Extraction receives only `{text}`. Atomization receives `{parents, original_text}`, with only screened parents in `parents`; neither request contains full agent input. Existing annotation fields are unchanged.

The selector reviews coordination/list punctuation, collection quantifiers, common unresolved references, reporting wrappers, bundled demographics and unlocated quotes. Selection is a request for review, not an instruction to split. There are explicit no-split examples for compound names, ranges, joint conditions and uncertain alternatives. Unselected parents pass through unchanged. Each selected parent must occur exactly once in the response; missing or duplicate IDs fail and retry. Selection reasons are stage metadata, not new atom attributes.

**40/128 initial parents (31.3%)** were selected. Seven records needed a second pass; three skipped it. The 88 unselected parents were not sent to atomization. Broad screening remains imperfect: `with` compounds and some modified references escape it; selected parents can also return still bundled. Candidate-only review cannot recover a proposition omitted in the first pass.

## Measurements

| Metric | Earlier v1 | Output-only candidates v3 |
|---|---:|---:|
| Scheduling | Serial | Six workers |
| Batch elapsed | 644.50 s | 177.93 s |
| Sum of per-attempt elapsed time | 644.34 s | 664.12 s |
| Attempts / successful attempts | 23 / 22 | 19 / 17 |
| Final mentions | 162 | 165 |
| Mentions with an exact target quote | 137/162 (84.6%) | 159/165 (96.4%) |
| Agent-output mentions with exact quote | 110/135 (81.5%) | 130/136 (95.6%) |
| Known Go allowance estimate | $0.07663 | $0.05493 + unknown timeout usage |

The v3 failures were a 120.33-second extraction timeout with no returned usage and a 76.50-second atomization response with a duplicate parent ID. Both retried successfully. Count their elapsed time; count the returned invalid response's tokens. The timeout's charge cannot be reconstructed. The v3 estimate is not a reconciled cash bill, and omitted cache fields are treated as zero, not verified zero use.

**Do not attribute the 3.6× batch speedup to the prompt or candidate filter.** Concurrency changed too. Aggregate API work did not fall in this sample. Successful-attempt work alone was 467.29 seconds, but excluding retries is not a production runtime estimate. A separate output-only/all-parent live arm was not run, so the individual effects of output-only input and candidate screening are not isolated.

Using the official M2.5 tokenizer, returned v3 blocks contain **21,610 thinking tokens and 17,400 formal tokens: 55.4% / 44.6%**. Successful attempts alone are 53.3% thinking. Their combined 39,010 differs from API output usage 39,082 by four tokens for each of 18 returned responses. This is an offline block count, not native reasoning billing; the timed-out response is unknown. Removing context did not demonstrate reduced thinking share (v1: 54.3% overall, 46.4% successful).

## Density and quality

| Agent-output corpus | Words | Output mentions | Mentions / 100 words |
|---|---:|---:|---:|
| Historical Perspectrum, 108 DeepSeek debates / 972 turns | 113,062 | 13,082 | 11.57 |
| Clinical v1, five outputs, raw | 875 | 135 | 15.43 |
| Clinical v1, excluding the 20 observed input-only imports | 875 | 115 | 13.14 |
| Clinical v3, same five outputs, raw | 875 | 136 | 15.54 |

Historical counts use every output mention in the `.v2.json` stores paired with original `.debate.json` text; they do not count only viewer-located spans or only canonical clusters. This is a descriptive density comparison across different protocols and datasets, not an extraction-recall comparison. Averaging all ten mixed-length records is misleading.

Manual reading of all 165 v3 mentions found no recurrence of the known 20 v1 context-only imports. Exact quoting improved substantially. Yet quoting is not semantic accuracy or completeness: some joint diagnostic grounds lose scope, symptoms lose duration, references remain ambiguous, and compounds remain bundled. Two S04 pairs are punctuation variants of the same findings. Such duplicates inflate counts even when quotes are valid. Some inference labels still omit laboratory/imaging/pathology, and diagnostic workup can be mislabeled treatment. Sources remain easier than interpretive outputs. No independent clinical gold or recall estimate exists for this sample.

## Full study: six-worker estimate

The frozen generation corpus has 1,080 agent outputs / 217,998 words. Across conditions there are 383 distinct original evidence segments / 6,506 words and 24 distinct common-metadata texts / 240 words. A reuse-aware extraction pass would process **1,487 records**, reusing sources across five conditions and metadata across agents. Extracting every visible input again is unnecessary; input profiles must union only the facts actually delivered under the saved visibility rules.

For each channel, multiply its measured per-record time by its full record count, sum, and divide by six. Repeat with per-word scaling as a sensitivity check. Do not multiply the ten-record batch wall time by a mixed record count: the sample overrepresents very short sources and has a substantial tail.

- Per-record scaling: **6.10 hours**, **$10.69 known allowance**.
- Per-word scaling: **6.83 hours**, **$11.87 known allowance**.
- Practical planning: roughly **7–9 hours**, with approximately **$11–15 allowance plus unreconciled timeout usage**, conditional on comparable load/retries. This is a planning range, not a statistical confidence interval or quota guarantee.
- A naive per-run invocation duplicates sources and metadata. Per-record extrapolation becomes **7.74 hours / $14.28 known allowance**, before queue and quota overhead. A cross-run reuse cache is not yet implemented: do not describe 6.10 hours as the unmodified runner's measured throughput.

These estimates cover extraction plus candidate atomization only, not local matching or judging. The sample's two failures dominate its variability; a larger pilot may change the estimate in either direction.

## Acceleration investigation

[MiniMax's current Anthropic API documentation](https://platform.minimax.io/docs/api-reference/text-anthropic-api#thinking-control) states that M2.x thinking cannot be disabled, whereas M3 supports disabling it. [OpenCode Go](https://opencode.ai/docs/go/) currently lists M3 and M2.5 at the same input/output rates ($0.30 / $1.20 per million), separately from Zen. Both tests used the Go API 2 endpoint. No direct-provider or metered fallback was used.

| Same two output texts, both stages | M2.5 v3 | M3, thinking disabled |
|---|---:|---:|
| S03 elapsed, including retries | 177.93 s | 20.56 s |
| S04 elapsed | 46.08 s | 20.39 s |
| Sum of successful-attempt work | 103.64 s | 40.92 s |
| Attempts | 5 | 4 |
| Located final mentions | 52/55 | 61/61 |
| Thinking blocks returned | Present | None |
| M3 output tokens / allowance | — | 6,704 / $0.01074 |

M3 was about **2.5× faster on successful-call work** for these two texts; the larger apparent wall-time gain includes M2.5's timeout. This two-worker test does not measure sustained six-worker throughput. Raw fact count increased partly through duplicate lab observations. It also split a jointly definitive clinical-and-imaging premise into two independently definitive claims. Thus 61/61 quote location does not validate its factual fidelity.

At the observed M3 mean, **the 1,080 outputs alone** imply 1.02 hours with six fully occupied workers; adjusting for full-corpus mean text length gives about 1.26 hours. Sources, metadata, queueing, retries and quota limits are additional and unmeasured for M3. A one-hour full-pipeline promise is unsupported.

Recommended next experiments, with the same atom schema:

1. M3 is the most concrete speed candidate, but first correct and evaluate joint-condition preservation and duplication on a broader paired sample. Keep its measurement version separate; do not silently switch the default.
2. Reduce wire-format repetition: return unchanged parent IDs rather than regenerating every annotation field, reconstructing those fields locally. Split children still need their own fields. This saves formal output without adding or deleting stored attributes; no latency/quality benchmark exists yet.
3. Implement provenance-preserving source/metadata reuse and a corpus-level queue capped at six requests. Avoid independent per-run pools that silently multiply concurrency. This removes redundant work rather than changing extracted meaning.
4. Direct MiniMax advertises M2.5-highspeed (~100 vs ~60 tokens/s), but that SKU is not listed in the inspected Go catalogue. It is not an available API-2-only solution without a separate provider arrangement, so no call was made.

## Code validation

55 offline tests passed, including output-only request boundaries, candidate screening, no-call passthrough, selected-ID coverage and preservation of unselected fields/order. Tests establish implementation invariants, not clinical extraction quality. Root reusable YAML presets now use candidate-only atomization and six workers; frozen historical run YAMLs remain unchanged.
