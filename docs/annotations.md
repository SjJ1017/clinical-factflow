# Clinical occurrence annotations

The vocabulary is an initial operational proposal, not a validated clinical ontology. Every extractor response is schema-validated; malformed or missing items fail the stage. The second atomization pass receives every parent, the original text and exactly the speaker-visible context, and must return at least one part for each parent.

| Axis | Values | Operational question |
|---|---|---|
| kind | observation, inference, recommendation, general_knowledge, discourse | What type of proposition did the speaker express? |
| attribution | direct, reported, unknown | Is it explicitly attributed to another speaker, patient or report? |
| certainty | asserted, probable, possible, conditional, unclear | How strongly is this occurrence presented? |
| polarity | affirmed, negated | Does the proposition explicitly deny something? |
| clinical_domain | history, examination, laboratory, imaging, pathology, diagnosis, treatment, other | What evidence or clinical activity does it concern? |
| attributed_to | text or null | Who or what was explicitly named as the source? |

"The patient reports no pain" is a **reported, negated observation**. "Agent B suggests pneumonia" is a **reported, possible inference**. "The CT report lacks a comparison scan" is a **discourse** claim about documentation, not a finding that the patient has no disease. A recommendation preserves its modality: "If bleeding persists, consider endoscopy" does not assert that an endoscopy occurred.

Do not remove uncertainty from proposition text just to make more matches. An assertion and a suspicion may have different entailment relations. The annotations describe how a statement was expressed; they do not supply a separate, hidden source of truth to the matcher.

All quotes reference the original text. A quote with several atomized children retains all children. Every exact occurrence of a quote is listed as `[start, end)` character offsets. When a quote occurs repeatedly, the location is ambiguous among those spans; all locations are candidates, not evidence of several separate utterances. Unlocated quotes remain visible as `span_status: unlocated`. Offsets are **character offsets**, not token positions.

To build interpretable profiles later, one can count observations vs inferences, uncertainty, pertinent negatives, numerical qualifiers, and actually available source/peer facts. Do not make the classifier's target answer or role label an extraction input. More importantly, **absent from the gold rationale does not mean false**. Truth assessment needs a separate, explicitly scoped reference and human checks, especially for recommendations and plausible alternate diagnoses.

Nonmedical work should introduce a versioned domain vocabulary with domain examples and independent validation. The runner and canonical evidence schema are reusable; the current clinical taxonomy should not be relabeled as a universal ontology.
