"""Sync state: what's already been imported into a specific vault.

Tracks two things, both scoped to one vault:

1. Which Codeforces submission ids have already been imported, so
   ``cp-handbook sync`` is safe to run repeatedly without ever creating
   a duplicate note for the same accepted submission.
2. Every previously-synced ``Problem``, serialized in full -- so the
   knowledge graph can be rebuilt over *everything* known so far on
   each run, not just this run's new items. Reading a KnowledgeItem
   back from its rendered Markdown (a real "vault loader") is out of
   scope here -- see the Chunk 4A architecture notes on
   ``handbook.graph`` -- so this package keeps its own record of what
   it has already written instead.

Persisted as plain JSON at ``<vault_root>/.handbook/sync/state.json``,
the same "small JSON file, atomic write" convention
:class:`~handbook.core.index.StorageIndex` already established for
storage's own bookkeeping.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from handbook.models import KnowledgeItem, Problem
from handbook.utils.filesystem import atomic_write

_STATE_RELATIVE_PATH = Path(".handbook") / "sync" / "state.json"


class SyncState:
    """One vault's Codeforces sync bookkeeping."""

    def __init__(self, vault_root: Path) -> None:
        self._path = vault_root / _STATE_RELATIVE_PATH
        self.handle: str | None = None
        self.last_synced_at: datetime | None = None
        self._imported_submission_ids: set[int] = set()
        self._items_by_problem_key: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self.handle = raw.get("handle")
        last_synced = raw.get("last_synced_at")
        self.last_synced_at = (
            datetime.fromisoformat(last_synced) if last_synced else None
        )
        self._imported_submission_ids = set(raw.get("imported_submission_ids", []))
        self._items_by_problem_key = raw.get("items", {})

    def save(self) -> None:
        payload = {
            "version": 1,
            "handle": self.handle,
            "last_synced_at": (
                self.last_synced_at.isoformat() if self.last_synced_at else None
            ),
            "imported_submission_ids": sorted(self._imported_submission_ids),
            "items": self._items_by_problem_key,
        }
        atomic_write(self._path, json.dumps(payload, indent=2, ensure_ascii=False))

    # -- submission dedup -------------------------------------------------
    def has_imported(self, submission_id: int) -> bool:
        """Has this exact Codeforces submission id already been processed?"""
        return submission_id in self._imported_submission_ids

    def mark_imported(self, submission_id: int) -> None:
        """Record that this submission id has been processed (accepted or
        not worth creating a new note for -- e.g. a second AC on a
        problem that's already known). Never reprocessed again."""
        self._imported_submission_ids.add(submission_id)

    def imported_count(self) -> int:
        return len(self._imported_submission_ids)

    # -- known problems -----------------------------------------------------
    def has_problem(self, problem_key: str) -> bool:
        """Does this vault already have a Problem note for this Codeforces problem?"""
        return problem_key in self._items_by_problem_key

    def remember_problem(self, problem_key: str, item: KnowledgeItem) -> None:
        """Record ``item`` as this vault's Problem note for ``problem_key``."""
        self._items_by_problem_key[problem_key] = item.model_dump(mode="json")

    def problem_count(self) -> int:
        return len(self._items_by_problem_key)

    def known_items(self) -> list[Problem]:
        """Every previously-synced Problem, reconstructed for a full graph rebuild.

        Reloaded from this state file, not from the vault's rendered
        Markdown -- see the module docs above on why.
        """
        return [
            Problem.model_validate(data) for data in self._items_by_problem_key.values()
        ]
