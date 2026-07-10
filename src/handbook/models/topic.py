"""Topic: a broad subject area hub (Graph Theory, Number Theory, ...)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from handbook.models.base import KnowledgeItem, Relation, coerce_relations
from handbook.models.enums import PatternCategory, RelationType


class Topic(KnowledgeItem):
    """The hub that groups algorithms, patterns, and benchmark problems
    under one subject area.

    Where Algorithm/Pattern/Problem/Mistake are leaf knowledge, Topic is
    what a future revision-scheduling or recommendation feature would
    query first ("what's my weakest topic?") before drilling into
    specific algorithms -- which is why it reuses the base ``status``
    field for mastery rather than inventing a parallel field.
    """

    KIND: ClassVar[str] = "topic"

    area: PatternCategory | None = None
    description: str = ""

    algorithms: list[Relation] = Field(default_factory=list)
    patterns: list[Relation] = Field(default_factory=list)
    key_problems: list[Relation] = Field(default_factory=list)
    """Representative/benchmark problems for this topic -- not every
    problem that touches it, just the ones worth revisiting."""

    @field_validator("algorithms", "patterns", mode="before")
    @classmethod
    def _coerce_children(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.CONTAINS)

    @field_validator("key_problems", mode="before")
    @classmethod
    def _coerce_problems(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.APPEARS_IN)
