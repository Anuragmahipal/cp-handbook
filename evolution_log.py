"""``EvolutionLog``: this vault's append-only history of
:class:`~handbook.evolution.events.LearningEvent`.

Persisted as JSON Lines at
``<vault_root>/.handbook/evolution/events.jsonl`` -- one event per
line, not one JSON array in a single blob. That format choice is not
cosmetic: :meth:`EvolutionLog.append` opens the file in append mode
(``"a"``) and writes exactly one new line. It never reads the file back
in to rewrite it whole, the way persisting a JSON array necessarily
would. "Running sync twice must never destroy history. Only append."
(this chunk's own words) is true at the *filesystem* level here, not
just as an invariant this module promises to maintain in memory --
there is no code path in this module that can truncate or overwrite a
previously-written line.

Mirrors the same "no vault loader, so keep our own record" reasoning
:class:`handbook.materialize.state.MaterializeState` already
established for materialized items -- except here, unlike
``MaterializeState``, there is nothing to protect from being
overwritten, because nothing is ever rewritten in the first place.
"""

from __future__ import annotations

import json
from pathlib import Path

from handbook.evolution.events import (
    EventKind,
    KnowledgeGrowth,
    LearningEvent,
    MasteryChange,
    TimelineEntry,
)
from handbook.learning.enums import ReviewStatus

_LOG_RELATIVE_PATH = Path(".handbook") / "evolution" / "events.jsonl"

_MODEL_BY_KIND: dict[EventKind, type[LearningEvent]] = {
    EventKind.SOLVED: LearningEvent,
    EventKind.ATTEMPTED: LearningEvent,
    EventKind.KNOWLEDGE_GROWTH: KnowledgeGrowth,
    EventKind.MASTERY_CHANGE: MasteryChange,
}


class EvolutionLog:
    """One vault's full learning history, loaded once and appended to
    as :class:`~handbook.evolution.engine.LearningEvolutionEngine`
    discovers new facts.
    """

    def __init__(self, vault_root: Path) -> None:
        self._path = vault_root / _LOG_RELATIVE_PATH
        self._events: list[LearningEvent] = []
        self._known_ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        for raw_line in self._path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            data = json.loads(line)
            model = _MODEL_BY_KIND[EventKind(data["kind"])]
            event = model.model_validate(data)
            self._events.append(event)
            self._known_ids.add(event.id)

    def has(self, event_id: str) -> bool:
        return event_id in self._known_ids

    def append(self, event: LearningEvent) -> bool:
        """Append ``event`` to the log, on disk, immediately.

        Returns ``True`` if it was newly recorded, ``False`` (writing
        nothing) if this exact ``event.id`` was already present -- the
        mechanism that makes re-running
        :class:`~handbook.evolution.engine.LearningEvolutionEngine`
        over the same data a no-op rather than a duplicate.
        """
        if event.id in self._known_ids:
            return False
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False))
            handle.write("\n")
        self._events.append(event)
        self._known_ids.add(event.id)
        return True

    def events(self) -> list[LearningEvent]:
        """Every event ever recorded, in the order they were appended
        (not necessarily chronological by ``when`` -- see
        :meth:`timeline_entries` for a sorted, display-ready view)."""
        return list(self._events)

    def events_for(self, item_id: str) -> list[LearningEvent]:
        return [event for event in self._events if event.item_id == item_id]

    def timeline_entries(self, item_id: str | None = None) -> list[TimelineEntry]:
        """Every event -- or every event about ``item_id`` -- as
        display-ready :class:`~handbook.evolution.events.TimelineEntry`
        objects, sorted chronologically."""
        source = self._events if item_id is None else self.events_for(item_id)
        entries = [TimelineEntry.from_event(event) for event in source]
        entries.sort(key=lambda entry: entry.when)
        return entries

    def latest_total_for(self, item_id: str) -> int:
        """The most recently recorded ``KnowledgeGrowth.new_total`` for
        ``item_id``, or ``0`` if none has ever been recorded -- the
        baseline :class:`~handbook.evolution.engine.
        LearningEvolutionEngine` diffs the live graph count against to
        decide whether growth actually happened this run."""
        growths = [event for event in self.events_for(item_id) if isinstance(event, KnowledgeGrowth)]
        if not growths:
            return 0
        return max(growths, key=lambda event: event.when).new_total

    def latest_mastery_for(self, item_id: str) -> ReviewStatus:
        """The most recently recorded mastery status for ``item_id``,
        or :attr:`~handbook.learning.enums.ReviewStatus.NEW` if none
        has ever been recorded."""
        changes = [event for event in self.events_for(item_id) if isinstance(event, MasteryChange)]
        if not changes:
            return ReviewStatus.NEW
        return max(changes, key=lambda event: event.when).new_status
