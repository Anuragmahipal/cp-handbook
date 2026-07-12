"""Retrieval cues and their review state.

Two objects, deliberately separated:

:class:`MemoryAnchor` is *content* -- authored once, part of the page,
    revised the same way any other content is. It's a compressed cue
    ("why lo = mid here, not mid + 1") pointing back at the block that
    holds the full explanation, rather than duplicating that
    explanation. This mirrors the "relations as data, not copies of
    content" philosophy already used for the domain model's typed
    relationships, and it directly encodes the generation-effect
    finding from the study-partner research: the cue is meant to make
    someone reconstruct the idea, not hand it back to them.

:class:`ReviewCue` is *state* -- how a specific anchor is doing over
    time for whoever is studying this page: new, due, mastered, how
    many times it's been reviewed, when it was last reviewed, when
    it's next due. This package stores that state; it does not
    implement the scheduling algorithm that computes ``next_due_at``
    from it. That's a deliberate boundary, matching this chunk's
    charter to build the representation, not an engine on top of it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from handbook.learning.enums import AnchorType, ReviewStatus
from handbook.learning.richtext import RichText
from handbook.learning.versioning import Identified


class MemoryAnchor(Identified):
    """A compressed retrieval cue for a specific piece of content."""

    target_id: str
    """The id of the block (or the owning ``Section`` itself) this
    anchor is a cue for. Resolving it to actual content is a reader's
    job, not this object's -- see the class docstring."""
    prompt: RichText
    anchor_type: AnchorType = AnchorType.KEYWORD


class ReviewCue(Identified):
    """The scheduling state of a review instance for one
    :class:`MemoryAnchor`.
    """

    anchor_id: str
    status: ReviewStatus = ReviewStatus.NEW
    strength: float = Field(default=0.0, ge=0.0, le=1.0)
    """A generic confidence signal in ``[0, 1]``. What updates it, and
    by how much, is a scheduling algorithm's concern -- this field only
    carries the current value."""
    review_count: int = Field(default=0, ge=0)
    last_reviewed_at: datetime | None = None
    next_due_at: datetime | None = None
