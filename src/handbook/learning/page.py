"""The document structure: :class:`PageMetadata`, :class:`Section`,
:class:`Page`.

A ``Page`` is the top-level, independently serializable unit of
learning content -- what a future renderer turns into one Markdown
note, one interactive canvas view, one stack of flashcards, one slide
deck, or one PDF page. A ``Section`` is a labeled, ordered chunk within
it (an "Intuition" section, a "Common Mistakes" section); a ``Page`` is
an ordered sequence of ``Section``.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from handbook.learning.blocks import Block
from handbook.learning.review import MemoryAnchor, ReviewCue
from handbook.learning.richtext import RichText
from handbook.learning.versioning import CURRENT_SCHEMA_VERSION, LIRModel, Revisable


def _dedupe_normalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    """Strip, lowercase, drop blanks, dedupe while preserving order.

    A small, local reimplementation of the same normalization
    ``handbook.models.base`` applies to ``KnowledgeItem.tags``, rather
    than an import from it -- this package does not depend on the
    domain model (see the package docstring for why).
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in tags:
        cleaned = raw.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return tuple(result)


class PageMetadata(LIRModel):
    """Descriptive metadata about a ``Page``, independent of its content."""

    title: str
    summary: str = ""
    tags: tuple[str, ...] = ()
    source_kind: str = ""
    """A free-form hint of what kind of thing this page originated
    from (e.g. ``"algorithm"``, ``"problem"``, ``"mistake"``).
    Deliberately a plain string rather than an import of the domain
    model's ``KnowledgeItem`` subclasses or any enum of theirs -- this
    package has no dependency on ``handbook.models``."""
    difficulty: str | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)
    locale: str = "en"

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("PageMetadata.title must not be blank")
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, v: object) -> object:
        if isinstance(v, (list, tuple)):
            return _dedupe_normalize_tags(tuple(v))
        return v


class Section(Revisable):
    """A labeled, ordered chunk of content within a ``Page``."""

    heading: RichText
    blocks: tuple[Block, ...] = ()
    memory_anchors: tuple[MemoryAnchor, ...] = ()
    review_cues: tuple[ReviewCue, ...] = ()

    @model_validator(mode="after")
    def _block_ids_are_unique(self) -> Section:
        ids = [block.id for block in self.blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("Section.blocks contains duplicate block ids")
        return self

    @model_validator(mode="after")
    def _memory_anchors_reference_known_targets(self) -> Section:
        valid_targets = {self.id} | {block.id for block in self.blocks}
        for anchor in self.memory_anchors:
            if anchor.target_id not in valid_targets:
                raise ValueError(
                    f"MemoryAnchor.target_id={anchor.target_id!r} does not "
                    f"match this Section's id or any of its block ids"
                )
        return self

    @model_validator(mode="after")
    def _review_cues_reference_known_anchors(self) -> Section:
        anchor_ids = {anchor.id for anchor in self.memory_anchors}
        for cue in self.review_cues:
            if cue.anchor_id not in anchor_ids:
                raise ValueError(
                    f"ReviewCue.anchor_id={cue.anchor_id!r} does not match "
                    f"any MemoryAnchor in this Section"
                )
        return self


class Page(Revisable):
    """The top-level, independently serializable unit of learning
    content: metadata plus an ordered sequence of sections.
    """

    metadata: PageMetadata
    sections: tuple[Section, ...] = ()
    schema_version: int = Field(default=CURRENT_SCHEMA_VERSION, frozen=True)

    @model_validator(mode="after")
    def _section_ids_are_unique(self) -> Page:
        ids = [section.id for section in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("Page.sections contains duplicate section ids")
        return self
