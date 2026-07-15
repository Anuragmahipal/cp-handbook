"""The event types ``handbook.evolution`` is built from.

These are history, not notes. A ``KnowledgeItem`` (``Algorithm``,
``Problem``, ...) is something a person authors and can freely rewrite
-- that's the whole point of ``handbook.materialize`` never touching a
materialized file twice. An event here is the opposite: an immutable
record of something that was true at a point in time. Once appended
(see :mod:`handbook.evolution.log`), it is never edited or deleted --
only ever added to. That distinction is what makes "the notebook
should become richer every week without losing previous knowledge"
(this chunk's own goal) a property of the data model, not just a
promise about how the code happens to behave today.

Three concrete kinds of fact are recorded:

``LearningEvent``
    The base fact, and also the concrete type for the simplest case --
    "this Problem was solved/attempted." Every other event kind
    inherits its shape (``id``, ``item_id``, ``when``, ``summary``).
``KnowledgeGrowth``
    An Algorithm/Pattern/Mistake gained more real-world use -- another
    Problem started referencing it. Carries the before/after count.
``MasteryChange``
    An item's review status (:class:`~handbook.learning.enums.
    ReviewStatus`, the same enum ``ReviewCue`` already uses -- see
    ``docs/ARCHITECTURE_NOTES_EVOLUTION.md`` for why this reuses that
    enum instead of inventing a second one) crossed a milestone.

``TimelineEntry`` is not a fourth *kind* of fact -- it is what any of
the above three look like once flattened for display: just a
``(when, item_id, label)``. Chronological-history sections (Part 4 of
this chunk) are built from a list of these, never from raw events
directly, so a rendering caller never needs to know or care which of
the three concrete event kinds produced a given line.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from handbook.learning.enums import ReviewStatus


class EventKind(StrEnum):
    SOLVED = "solved"
    ATTEMPTED = "attempted"
    KNOWLEDGE_GROWTH = "knowledge_growth"
    MASTERY_CHANGE = "mastery_change"


class LearningEvent(BaseModel):
    """One immutable fact: ``item_id`` had something happen to it, at
    ``when``. The base type for every event kind in this module, and
    the concrete type used directly for the simplest kind --
    ``EventKind.SOLVED``/``EventKind.ATTEMPTED``.

    ``id`` is a deterministic identifier (see
    :mod:`handbook.evolution.engine`), never a random one -- it is what
    lets :meth:`handbook.evolution.log.EvolutionLog.append` recognize
    "this exact fact is already recorded" and skip re-appending it,
    which is the entire mechanism behind "running sync twice must
    never destroy history" *and* must never duplicate it either.
    """

    id: str
    kind: EventKind
    item_id: str
    when: datetime
    summary: str


class KnowledgeGrowth(LearningEvent):
    """``item_id`` (an Algorithm/Pattern/Mistake) is now used by more
    problems than the last time this was recorded."""

    kind: Literal[EventKind.KNOWLEDGE_GROWTH] = EventKind.KNOWLEDGE_GROWTH
    previous_total: int
    new_total: int


class MasteryChange(LearningEvent):
    """``item_id``'s review status crossed a milestone -- see
    :func:`handbook.evolution.engine.mastery_for_count` for the
    deterministic rule that decides when."""

    kind: Literal[EventKind.MASTERY_CHANGE] = EventKind.MASTERY_CHANGE
    previous_status: ReviewStatus
    new_status: ReviewStatus


class TimelineEntry(BaseModel):
    """A read-only, display-ready projection of one event -- what a
    chronological history section actually renders.

    Deliberately not a ``LearningEvent`` subtype: a ``TimelineEntry``
    can be produced uniformly from any of the three event kinds above,
    and only ever carries what rendering needs (when it happened, which
    item it's about, one line describing it) -- never that event's own
    kind-specific structured payload (``previous_total``,
    ``new_status``, ...). Keeping the two separate means a rendering
    caller (a compiler section, a dashboard card) only ever has to
    understand one shape, regardless of how many kinds of fact
    ``handbook.evolution`` learns to record in the future.
    """

    when: datetime
    item_id: str
    label: str

    @classmethod
    def from_event(cls, event: LearningEvent) -> TimelineEntry:
        return cls(when=event.when, item_id=event.item_id, label=event.summary)
