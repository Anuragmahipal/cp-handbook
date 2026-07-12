"""Cross-page sequencing.

A :class:`LearningPath` is an ordered curriculum: "learn this page,
then this section of that page, then this other page." Order is
carried implicitly by list position in ``steps`` rather than an
explicit integer field on each step -- inserting a step between two
others is then just a matter of where it sits in the tuple, with
nothing else to keep in sync.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from handbook.learning.versioning import CURRENT_SCHEMA_VERSION, Identified, Revisable


class PathStep(Identified):
    """One stop on a :class:`LearningPath`."""

    page_id: str
    section_id: str | None = None
    """When set, this step points at one section of ``page_id`` rather
    than the whole page -- e.g. "just the Common Mistakes section of
    this page, you've already covered the rest"."""
    rationale: str = ""
    optional: bool = False


class LearningPath(Revisable):
    """An ordered sequence of :class:`PathStep` across one or more
    ``Page`` objects.
    """

    title: str
    description: str = ""
    steps: tuple[PathStep, ...] = ()
    schema_version: int = Field(default=CURRENT_SCHEMA_VERSION, frozen=True)

    @model_validator(mode="after")
    def _title_not_blank(self) -> LearningPath:
        if not self.title.strip():
            raise ValueError("LearningPath.title must not be blank")
        return self

    @model_validator(mode="after")
    def _step_ids_are_unique(self) -> LearningPath:
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("LearningPath.steps contains duplicate step ids")
        return self
