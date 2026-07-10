"""Mistake: a specific, recurring error worth remembering and avoiding."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from handbook.models.base import KnowledgeItem, Relation, coerce_relations
from handbook.models.enums import MistakeCategory, RelationType


class Mistake(KnowledgeItem):
    """A recurring error: what happened, why, and how to prevent it."""

    KIND: ClassVar[str] = "mistake"

    category: MistakeCategory = MistakeCategory.OTHER

    cause: str = ""
    prevention: str = ""

    occurrences: int = Field(default=1, ge=1)
    """How many times this mistake has been made. Storing the same
    ``Mistake`` id again (see the storage engine's duplicate policy) is
    the expected way to bump this, rather than creating a near-duplicate
    entry each time it recurs."""

    related_problems: list[Relation] = Field(default_factory=list)
    related_algorithms: list[Relation] = Field(default_factory=list)

    @field_validator("related_problems", mode="before")
    @classmethod
    def _coerce_problems(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.APPEARS_IN)

    @field_validator("related_algorithms", mode="before")
    @classmethod
    def _coerce_algorithms(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.RELATED)
