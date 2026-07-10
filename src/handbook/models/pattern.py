"""Pattern: a recurring problem-solving pattern (Two Pointers, Sliding Window, ...)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from handbook.models.base import KnowledgeItem, Relation, coerce_relations
from handbook.models.enums import PatternCategory, RelationType


class Pattern(KnowledgeItem):
    """A way of *recognizing and approaching* a class of problems.

    Distinct from :class:`~handbook.models.algorithm.Algorithm`: a
    pattern is a recognition strategy, not one canonical implementation.
    """

    KIND: ClassVar[str] = "pattern"

    category: PatternCategory | None = None
    description: str = ""

    recognition_cues: list[str] = Field(default_factory=list)
    """Telltale signs in a problem statement that hint this pattern
    applies, e.g. 'sorted array' + 'pair sum' -> Two Pointers."""

    related_algorithms: list[Relation] = Field(default_factory=list)
    example_problems: list[Relation] = Field(default_factory=list)

    @field_validator("recognition_cues")
    @classmethod
    def _dedupe_cues(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in v:
            cleaned = item.strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                result.append(cleaned)
        return result

    @field_validator("related_algorithms", mode="before")
    @classmethod
    def _coerce_algorithms(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.USES)

    @field_validator("example_problems", mode="before")
    @classmethod
    def _coerce_problems(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.APPEARS_IN)
