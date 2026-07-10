"""Contest: a specific contest event (a Codeforces round, an ICPC regional, ...)."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import Field, field_validator

from handbook.models.base import KnowledgeItem, Relation, coerce_relations
from handbook.models.enums import ContestType, Platform, RelationType


class Contest(KnowledgeItem):
    """Groups the problems attempted in one sitting and records how it
    went, so performance trends and post-contest reflections are
    queryable data rather than buried inside individual problem notes.
    """

    KIND: ClassVar[str] = "contest"

    platform: Platform
    contest_type: ContestType = ContestType.RATED

    start_time: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    url: str = ""

    problems: list[Relation] = Field(default_factory=list)
    """Problems that appeared in this contest. Plain strings are
    accepted and coerced to ``Relation(type=CONTAINS)``."""

    rank: int | None = Field(default=None, ge=1)
    rating_change: int | None = None
    performance_rating: int | None = Field(default=None, gt=0)

    takeaways: list[str] = Field(default_factory=list)
    """Short, distinct lessons from this contest -- separate from the
    inherited free-form ``notes``, since takeaways are meant to be
    scannable bullet points a revision feature could resurface later."""

    @field_validator("problems", mode="before")
    @classmethod
    def _coerce_problems(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.CONTAINS)

    @field_validator("takeaways")
    @classmethod
    def _dedupe_takeaways(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in v:
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result
