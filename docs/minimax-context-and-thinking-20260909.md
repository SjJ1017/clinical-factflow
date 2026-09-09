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
