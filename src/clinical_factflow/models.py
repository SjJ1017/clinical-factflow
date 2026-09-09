from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Strict):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    category: str
    source_field: str


class Case(Strict):
    id: str
    question: str
    evidence: list[Evidence]
    reference: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_sources(self):
        if not self.evidence or len({x.id for x in self.evidence}) != len(self.evidence):
            raise ValueError("Cases need nonempty evidence with unique source IDs")
        return self


class Annotation(Strict):
    kind: Literal["observation", "inference", "recommendation", "general_knowledge", "discourse"]
    attribution: Literal["direct", "reported", "unknown"]
    certainty: Literal["asserted", "probable", "possible", "conditional", "unclear"]
    polarity: Literal["affirmed", "negated"]
    clinical_domain: Literal["history", "examination", "laboratory", "imaging", "pathology", "diagnosis", "treatment", "other"]
    attributed_to: str | None = None


class Atom(Strict):
    text: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    qualifiers: list[str]
    annotation: Annotation


class Extracted(Strict):
    facts: list[Atom]


class SplitItem(Strict):
    parent_id: str
    parts: list[Atom] = Field(min_length=1)


class SplitResult(Strict):
    facts: list[SplitItem]


class AgentAnswer(Strict):
    assessment: str = Field(min_length=1)
    answer: str = Field(min_length=1)
