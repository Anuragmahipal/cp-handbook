"""Algorithm: a named algorithmic technique (Binary Lifting, Segment Tree, ...)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from handbook.models.base import KnowledgeItem, Relation, coerce_relations
from handbook.models.enums import PatternCategory, RelationType


class Algorithm(KnowledgeItem):
    """Captures the *why* (intuition), the *how* (implementation and
    complexity), and the *where it bites you* (pitfalls) for a technique
    -- the three things worth remembering years after first learning it.
    """

    KIND: ClassVar[str] = "algorithm"

    category: PatternCategory | None = None

    time_complexity: str = ""
    space_complexity: str = ""

    intuition: str = ""
    implementation: str = ""

    pitfalls: list[str] = Field(default_factory=list)

    related_problems: list[Relation] = Field(default_factory=list)
    """Problems this algorithm solves or appears in. Plain strings are
    accepted and coerced to ``Relation(type=APPEARS_IN)``."""

    @field_validator("pitfalls")
    @classmethod
    def _dedupe_pitfalls(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in v:
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result

    @field_validator("related_problems", mode="before")
    @classmethod
    def _coerce_related_problems(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.APPEARS_IN)
