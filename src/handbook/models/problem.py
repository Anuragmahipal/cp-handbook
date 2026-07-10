"""Problem: a specific problem attempted or solved on some platform."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from handbook.models.base import KnowledgeItem, Relation, coerce_relations
from handbook.models.enums import Platform, ProblemSource, RelationType


class Problem(KnowledgeItem):
    """A single problem instance: which platform, which contest, which
    algorithms/patterns it drew on, and whether/how it was solved.
    """

    KIND: ClassVar[str] = "problem"

    platform: Platform
    contest: str
    index: str

    contest_id: str | None = None
    """Id/title of the related :class:`~handbook.models.contest.Contest`,
    when this problem was attempted as part of one."""

    url: str = ""
    rating: int | None = Field(default=None, gt=0)
    source: ProblemSource = ProblemSource.PRACTICE

    algorithms: list[Relation] = Field(default_factory=list)
    patterns: list[Relation] = Field(default_factory=list)
    mistakes: list[Relation] = Field(default_factory=list)

    solved: bool = True
    attempts: int = Field(default=1, ge=0)
    time_spent_minutes: int | None = Field(default=None, ge=0)

    @field_validator("contest", "index")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("algorithms", "patterns", mode="before")
    @classmethod
    def _coerce_uses(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.USES)

    @field_validator("mistakes", mode="before")
    @classmethod
    def _coerce_mistakes(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.RELATED)
