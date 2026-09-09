# Extraction context and MiniMax thinking audit — 2026-09-09

## Why input facts appeared in output extraction

The previous implementation explicitly sent two objects to the first pass:
`text` (current output) and `reference_context` (the complete user message the
agent received, including initial case reports, its own earlier outputs and
received peer outputs). The second pass received that same context alongside
`parents` and `original_text`. The purpose was reference resolution, but a prompt
prohibition did not enforce the boundary between context and extractable text.
This was a pipeline design problem as well as model noncompliance.

The runner was not independently extracting each whole input prompt as a separate
channel. It extracted original evidence, shared metadata and outputs separately,
but exposing full input as an auxiliary context still allowed input-only facts
to contaminate output extraction.

Output extraction should receive only the output. Visible input facts can be
assembled from already-extracted records:

`visible input facts = visible initial-evidence facts ∪ common-metadata facts ∪ visible self-output facts ∪ delivered peer-output facts`.

The set is restricted to the **actual delivery records**, not all prior rounds
indiscriminately. In this study, original evidence remains visible every round,
own history is all previous rounds and peer history is the immediately preceding
round. Source evidence and metadata require their own initial extraction; those
facts do not originate in agent outputs. Reusing these records requires no fresh
LLM extraction of the composed input. Preserve occurrence provenance when taking
a semantic union so shared sources are not mistaken for peer transmissions.
Shared source/metadata extraction can be deduplicated across conditions under the
same text and measurement version; this audit does not implement a new global
cross-run cache or a full-corpus input-profile analysis.

## Correction to the previous stage attribution

The total of **20 context-only final mentions** is unchanged. The earlier report
attributed 19 to contaminated first-pass text and one to an independent
atomization addition. Inspecting the thinking and **all parent fields** showed
that the latter symptom claim was already present in `p0.qualifiers`. Atomization
promoted the contaminated qualifier to an independent fact. Thus all 20 are
traceable to the first-pass text or qualifiers. Another first-pass qualifier
(`p11`) also imported a number from context, although it did not survive into
the final atom. Exact quote location alone cannot validate the entire atom or
its qualifiers.

The original raw calls, results and first audit remain unchanged. The correction
and complete per-call thinking accounting are stored separately in
`runs/minimax-extraction-pilot-20260909/context-thinking-audit.json`.

## What the returned thinking contains

All **23/23 calls** emitted nonempty thinking. Together they returned **136,016
thinking characters** and **94,799 formal-output characters**. The API reports
**51,207 total output tokens**, not 51,207 reasoning tokens. It does not expose a
reliable reasoning/formal token split for these calls. Character counts are not
a substitute for tokenizer-based counts.

The worst call was the first extraction of S03 (a 161-word output). It generated
**36,286 thinking characters** but only **932 formal characters**, reached the
8,000-output-token cap and failed after **95.9 seconds**. The unchanged retry
succeeded. The failed response was dominated by repeated annotation planning:
relisting candidate facts, reconsidering negation, direct/reported attribution,
observation/inference/discourse classification, compound splitting and exact
quote boundaries. Its thinking contained 20 instances of “Let me”, 12 of “wait”,
90 mentions of attribution and 86 of quote. These are literal string counts,
not reasoning-step counts or a causal attribution of token cost.

Other inspected responses showed the same type of deliberation on smaller
scales. Even the short shared-metadata record generated 1,938 thinking characters
in extraction and 2,324 in atomization. In the contaminated S04 response, the
second pass treated a first-pass qualifier as an additional symptom observation.
Its review of already-contaminated parents expanded the result substantially.

The supported explanations are:

- The schema still asks for several existing annotation axes and exact quoting,
  and both passes reconsider them. The model spends substantial visible thinking
  resolving their boundaries, sometimes cycling through alternative drafts.
- A full second pass also emits each child as a complete JSON object. That formal
  serialization contributes output tokens independently of reasoning.
- Full auxiliary context offered more material to resolve and accidentally import.
  This mechanism is visible in the records, but there is no controlled comparison
  quantifying how much context removal will reduce reasoning.
- Requests set `max_tokens: 8000` and no separate thinking budget. This is a total
  generation ceiling, not a guarantee of short thinking or enough space for JSON.

[MiniMax's current Anthropic compatibility documentation](https://platform.minimax.io/docs/api-reference/text-anthropic-api#thinking-control)
states that thinking cannot be disabled for M2.x, including M2.5; a disabled
setting is accepted but does not turn thinking off. This is the model provider's
documentation, not an additional live test of OpenCode Go parameter forwarding.
The model was not switched and no unsupported budget control was asserted.

## Implemented boundary correction

The new `clinical-domain-multilabel-output-only-v2` configuration preserves all
atom fields and domain values. First-pass requests contain only `text`.
Second-pass requests contain only `parents` and `original_text`. Legacy record
objects may still contain `reference_context`, but the request builder ignores it.
New record construction does not copy generation messages or the task prompt.

Examples now resolve references within the target text; if a referent is absent,
the model must preserve ambiguity rather than fill it from another message or
clinical knowledge. Prompts also request brief, single-pass reasoning and warn
that intermediate qualifiers are not independent evidence. This wording is not
a hard thinking-token control. It has **not been validated with new paid calls**.

Regression tests confirm that source context, prior turns and reference labels
cannot reach either request through a legacy `reference_context`, and that output
records can be built without reading generation messages. **46 offline tests
pass**. These prove the transport boundary, not model extraction quality.

The 120 completed diagnosis traces and the completed MiniMax pilot remain frozen.
No new API calls, full extraction, matching or outcome judging were performed.


## Offline token split and old-pipeline comparison

The provider still exposes no thinking/formal usage split. A subsequent offline
count used the official [MiniMax M2.5 tokenizer](https://huggingface.co/MiniMaxAI/MiniMax-M2.5/tree/f710177d938eff80b684d42c5aa84b382612f21f),
revision `f710177d938eff80b684d42c5aa84b382612f21f`. Only tokenizer data files
were downloaded, with no model weights or remote-code execution. Each saved
thinking/text block was encoded separately with special tokens disabled.

| Calls included | Thinking tokens (offline) | Formal JSON tokens (offline) | Thinking share |
|---|---:|---:|---:|
| All 23 attempts | 27,776 | 23,339 | 54.3% |
| Initial extraction, 11 attempts | 15,608 | 8,734 | 64.1% |
| Atomization, 12 attempts | 12,168 | 14,605 | 45.4% |
| Successful attempts only, 22 | 20,011 | 23,108 | 46.4% |
| Failed truncation, 1 | 7,765 | 231 | 97.1% |

The offline sum is 51,115 versus 51,207 billed output tokens, a difference of
92 (0.18%): exactly four tokens per call. The difference plausibly reflects
framing/control tokens, but its precise attribution is unverified. These are
tokenizer-based estimates, not invented provider usage fields. Official tokenizer
files, hashes and every per-call count are archived in the private study's
`tokenizer-audit/` directory. No new generation/extraction calls were made.

Inspection of the original project's `experiments/retrace.py` and
`src/factflow/atomize.py` found several material execution differences:

- The old retrace entry point defaults to six concurrent calls, versus one in
  the clinical pilot. Old slots and atomization batches use bounded parallel maps.
- Old atomization regex-prefilters candidates by default and batches their fact
  sentences across a run; the clinical pipeline reviews every parent and batches
  within each record. The old prefilter has documented missed-splitting defects,
  so its speed cannot be adopted as evidence that its quality is adequate.
- Old atomization emits only an ID and a list of strings; the clinical pipeline
  emits complete annotated atoms and quotes again. With the *same* saved child
  sentences and identical compact JSON formatting, full objects require 11,999
  tokenizer tokens versus 3,105 for an ID/string-only representation (3.86×).
  This is a serialization comparison, not an observed speedup: deleting those
  fields would change the task, and no schema fields were deleted.

Thus the serial 35–45-hour budget extrapolation is not an appropriate optimized
execution plan, and excessive thinking alone does not explain the discrepancy
with the user's previous roughly one-hour workflow. Removing all thinking would
reduce observed generated-token volume by about 54%, not by tens of times.
Concurrency, per-record overhead, atomization scope and repeated serialization
also matter. The historical one-hour workload and exact launch arguments have
not been identified, so an equal-workload runtime ratio or a new one-hour promise
would be unsupported. Retain the atom structure while testing bounded concurrency
and reducing redundant second-pass output before setting a full-run schedule.
