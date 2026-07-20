"""``LearningEvolutionEngine``: turns "what does the vault look like
right now" into "what changed since I last looked", recorded as
:class:`~handbook.evolution.events.LearningEvent` s.

This is the only piece of ``handbook.evolution`` that writes anything.
Everything in :mod:`handbook.evolution.stats` is a pure, side-effect-
free read; everything in :mod:`handbook.evolution.log` just stores
whatever it's handed. This module is where "does this count as new
history" gets decided -- and it decides that the same way on every
call, given the same inputs, which is what makes it safe to call after
every single ``cp-handbook sync``, including ones that imported nothing
new.

How "what changed" is detected, without a diff
------------------------------------------------
There is no stored "previous state of the vault" to diff against.
Instead, every fact this engine might record is given a *deterministic*
id (``uuid5``, not random -- see :func:`_solved_event_id` and friends)
derived from what the fact actually says: which problem, which item,
which milestone value. Recording the same fact twice produces the same
id twice, and :meth:`~handbook.evolution.log.EvolutionLog.append`
already refuses to write a duplicate id. So this engine doesn't need to
track "have I seen this Problem before" itself -- it can simply *try*
to record every fact that's true right now, every single run, and let
the log's own idempotency filter out everything that hasn't changed.
Only genuinely new facts (a problem synced for the first time, a
count that's grown, a status that's advanced) ever result in a new
line being written.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID, uuid5

from handbook.evolution.events import EventKind, KnowledgeGrowth, LearningEvent, MasteryChange
from handbook.evolution.log import EvolutionLog
from handbook.graph import KnowledgeGraph
from handbook.learning.enums import ReviewStatus
from handbook.models.base import KnowledgeItem

_ID_NAMESPACE = UUID("d3a9c1b2-4e7f-4a2c-9d1b-6f8e2c3a5b7d")
"""Distinct from ``handbook.materialize.engine``'s own namespace UUID --
same technique, different constant, so a materialized item's id and an
event id about that same item can never collide even though both are
``uuid5``-derived from related strings."""

_GROWTH_FIELD_BY_KIND: dict[str, str] = {
    "algorithm": "algorithms",
    "pattern": "patterns",
    "mistake": "mistakes",
}
"""Which ``Problem`` relation field, when it points at this kind of
item, counts as "this problem uses it" -- the same field-to-kind
mapping ``handbook.materialize.engine`` uses for materialization,
reused here for growth tracking rather than redefined."""

_MASTERY_THRESHOLDS: tuple[tuple[int, ReviewStatus], ...] = (
    (0, ReviewStatus.NEW),
    (1, ReviewStatus.LEARNING),
    (3, ReviewStatus.DUE),
    (5, ReviewStatus.MASTERED),
)
"""The deterministic rule :func:`mastery_for_count` applies. Monotonic
in solve count alone -- no recency decay, no "forgetting" -- which is a
real, documented limitation (see
``docs/ARCHITECTURE_NOTES_EVOLUTION.md``), not an oversight: a decaying
estimate would need a notion of "now" this engine deliberately doesn't
have (see :mod:`handbook.evolution.stats` on anchoring to the vault's
own latest activity instead of wall-clock time), and a fixed threshold
table is something a person can actually predict and disagree with,
which a hidden decay curve is not.
"""


def mastery_for_count(count: int) -> ReviewStatus:
    """The review status implied by ``count`` distinct problems solved
    using an item. Reuses :class:`~handbook.learning.enums.ReviewStatus`
    -- the same enum ``ReviewCue`` already carries -- rather than
    inventing a second mastery vocabulary; see
    ``docs/ARCHITECTURE_NOTES_EVOLUTION.md``.
    """
    status = ReviewStatus.NEW
    for threshold, candidate in _MASTERY_THRESHOLDS:
        if count >= threshold:
            status = candidate
    return status


def _solved_event_id(problem_id: str, creation_time_seconds: int) -> str:
    """Deterministic id from problem id AND the submission timestamp.

    Using the raw creationTimeSeconds (not a formatted datetime) ensures
    the id is stable across timezones and string-format changes. Two
    events for the same problem at different times get different ids;
    the same event replayed gets the same id.
    """
    return str(uuid5(_ID_NAMESPACE, f"solved:{problem_id}:{creation_time_seconds}"))


def _growth_event_id(item_id: str, new_total: int) -> str:
    return str(uuid5(_ID_NAMESPACE, f"growth:{item_id}:{new_total}"))


def _mastery_event_id(item_id: str, status: ReviewStatus) -> str:
    return str(uuid5(_ID_NAMESPACE, f"mastery:{item_id}:{status.value}"))


def _backlink_count(graph: KnowledgeGraph, item_id: str, field_name: str) -> int:
    if graph.get(item_id) is None:
        return 0
    provenance = f"field:{field_name}"
    return sum(
        1 for edge, _node in graph.related(item_id, direction="in") if edge.provenance == provenance
    )


def _latest_backlink_time(graph: KnowledgeGraph, item_id: str, field_name: str, items_by_id: dict):
    if graph.get(item_id) is None:
        return None
    provenance = f"field:{field_name}"
    times = []
    for edge, node in graph.related(item_id, direction="in"):
        if edge.provenance != provenance:
            continue
        item = items_by_id.get(node.id)
        if item is not None:
            # For Problems, use solved_at (historical) not created_at
            if hasattr(item, "solved_at") and item.solved_at is not None:
                times.append(item.solved_at)
            else:
                times.append(item.created_at)
    return max(times) if times else None


@dataclass(frozen=True, slots=True)
class EvolutionReport:
    """What one :meth:`LearningEvolutionEngine.evolve` call actually
    recorded -- for :class:`handbook.sync.pipeline.SyncReport` and the
    CLI, not a second copy of the log itself."""

    learning_events: list[LearningEvent] = field(default_factory=list)
    knowledge_growth: list[KnowledgeGrowth] = field(default_factory=list)
    mastery_changes: list[MasteryChange] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.learning_events or self.knowledge_growth or self.mastery_changes)


class LearningEvolutionEngine:
    """Records this run's :class:`~handbook.evolution.events.LearningEvent` s
    into an :class:`~handbook.evolution.log.EvolutionLog`.

    Args:
        log: The vault's evolution log, already loaded (typically
            ``EvolutionLog(vault_root)``) -- shared with, not owned by,
            this engine, so a caller can inspect it (e.g. to hand it to
            ``KnowledgeCompiler``/``build_notebook_site`` for rendering)
            without going through this engine at all.
    """

    def __init__(self, log: EvolutionLog) -> None:
        self._log = log

    def evolve(
        self, items: Sequence[KnowledgeItem], graph: KnowledgeGraph
    ) -> EvolutionReport:
        """Record every fact currently true about ``items``/``graph``
        that isn't already in the log (see the module docstring on how
        "already in the log" is decided without a diff).

        ``items`` and ``graph`` are expected to be this run's full
        known set -- typically Problems plus whatever
        ``MaterializationEngine`` produced, and a graph built over
        that same set -- the same convention
        ``handbook.sync.notebook_site.build_notebook_site`` uses, for
        the same reason: relations need to resolve to real nodes, not
        shadows, for backlink counts to mean anything.
        """
        items_by_id = {item.id: item for item in items}
        learning_events = self._record_problem_events(items)
        knowledge_growth, mastery_changes = self._record_growth_and_mastery(
            items, graph, items_by_id
        )
        return EvolutionReport(
            learning_events=learning_events,
            knowledge_growth=knowledge_growth,
            mastery_changes=mastery_changes,
        )

    def _record_problem_events(self, items: Sequence[KnowledgeItem]) -> list[LearningEvent]:
        recorded: list[LearningEvent] = []
        for item in items:
            if item.kind != "problem":
                continue

            # Use historical timestamps from the Problem, not sync time
            solved = getattr(item, "solved", True)
            kind = EventKind.SOLVED if solved else EventKind.ATTEMPTED
            verb = "Solved" if solved else "Attempted"

            # When: solved_at for solved problems, first_attempted_at for unsolved
            if solved and hasattr(item, "solved_at") and item.solved_at is not None:
                when = item.solved_at
                creation_time_seconds = int(when.timestamp())
            elif hasattr(item, "first_attempted_at") and item.first_attempted_at is not None:
                when = item.first_attempted_at
                creation_time_seconds = int(when.timestamp())
            else:
                when = item.created_at
                creation_time_seconds = int(when.timestamp())

            event = LearningEvent(
                id=_solved_event_id(item.id, creation_time_seconds),
                kind=kind,
                item_id=item.id,
                when=when,
                summary=f"{verb} {item.title}",
            )
            if self._log.append(event):
                recorded.append(event)
        return recorded

    def _record_growth_and_mastery(
        self,
        items: Sequence[KnowledgeItem],
        graph: KnowledgeGraph,
        items_by_id: dict[str, KnowledgeItem],
    ) -> tuple[list[KnowledgeGrowth], list[MasteryChange]]:
        growth_recorded: list[KnowledgeGrowth] = []
        mastery_recorded: list[MasteryChange] = []

        for item in items:
            field_name = _GROWTH_FIELD_BY_KIND.get(item.kind)
            if field_name is None:
                continue

            current_total = _backlink_count(graph, item.id, field_name)
            previous_total = self._log.latest_total_for(item.id)
            growth_when = _latest_backlink_time(graph, item.id, field_name, items_by_id)
            fallback_when = growth_when or item.updated_at

            if current_total > previous_total:
                delta = current_total - previous_total
                event = KnowledgeGrowth(
                    id=_growth_event_id(item.id, current_total),
                    item_id=item.id,
                    when=fallback_when,
                    summary=(
                        f"{item.title}: now used by {current_total} "
                        f"problem{'s' if current_total != 1 else ''} (+{delta})"
                    ),
                    previous_total=previous_total,
                    new_total=current_total,
                )
                if self._log.append(event):
                    growth_recorded.append(event)

            new_status = mastery_for_count(current_total)
            previous_status = self._log.latest_mastery_for(item.id)
            if new_status != previous_status:
                event = MasteryChange(
                    id=_mastery_event_id(item.id, new_status),
                    item_id=item.id,
                    when=fallback_when,
                    summary=(
                        f"{item.title}: mastery {previous_status.value} → {new_status.value}"
                    ),
                    previous_status=previous_status,
                    new_status=new_status,
                )
                if self._log.append(event):
                    mastery_recorded.append(event)

        return growth_recorded, mastery_recorded
