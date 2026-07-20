"""Sync state: what's already been imported into a specific vault.

Tracks three things, all scoped to one vault:

1. Which Codeforces submission ids have already been imported, so
   ``cp-handbook sync`` is safe to run repeatedly without ever creating
   a duplicate note for the same submission.
2. Every previously-synced ``Problem``, serialized in full -- so the
   knowledge graph can be rebuilt over *everything* known so far on
   each run, not just this run's new items.
3. Every ``Submission`` record (accepted or not) -- the raw historical
   data from which all derived facts (attempt counts, solve times,
   streaks) are computed.

Persisted as plain JSON at ``<vault_root>/.handbook/sync/state.json``,
the same "small JSON file, atomic write" convention
:class:`~handbook.core.index.StorageIndex` already established for
storage's own bookkeeping.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from handbook.models import KnowledgeItem, Problem, Submission
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
        self._submissions_by_id: dict[int, dict] = {}
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
        # v2: full submission records
        self._submissions_by_id = {
            int(k): v for k, v in raw.get("submissions", {}).items()
        }

    def save(self) -> None:
        payload = {
            "version": 2,
            "handle": self.handle,
            "last_synced_at": (
                self.last_synced_at.isoformat() if self.last_synced_at else None
            ),
            "imported_submission_ids": sorted(self._imported_submission_ids),
            "items": self._items_by_problem_key,
            "submissions": self._submissions_by_id,
        }
        atomic_write(self._path, json.dumps(payload, indent=2, ensure_ascii=False))

    # -- submission dedup -------------------------------------------------
    def has_imported(self, submission_id: int) -> bool:
        """Has this exact Codeforces submission id already been processed?"""
        return submission_id in self._imported_submission_ids

    def mark_imported(self, submission_id: int) -> None:
        """Record that this submission id has been processed."""
        self._imported_submission_ids.add(submission_id)

    def imported_count(self) -> int:
        return len(self._imported_submission_ids)

    # -- full submission storage ------------------------------------------
    def store_submission(self, submission: Submission) -> None:
        """Persist a full submission record."""
        self._submissions_by_id[submission.id] = submission.to_dict()
        self.mark_imported(submission.id)

    def get_submission(self, submission_id: int) -> Submission | None:
        """Retrieve a previously stored submission by id."""
        data = self._submissions_by_id.get(submission_id)
        if data is None:
            return None
        return Submission.from_dict(data)

    def all_submissions(self) -> list[Submission]:
        """Every stored submission, in chronological order."""
        subs = [Submission.from_dict(d) for d in self._submissions_by_id.values()]
        return sorted(subs, key=lambda s: s.creation_time_seconds)

    def submissions_for_problem(self, problem_key: str) -> list[Submission]:
        """All submissions for a specific problem, in chronological order."""
        return [
            s for s in self.all_submissions() if s.problem_key == problem_key
        ]

    # -- problem tracking -------------------------------------------------
    def has_problem(self, problem_key: str) -> bool:
        return problem_key in self._items_by_problem_key

    def remember_problem(self, problem_key: str, item: Problem) -> None:
        """Serialize ``item`` so the graph can be rebuilt later."""
        self._items_by_problem_key[problem_key] = item.model_dump(mode="json")

    def known_items(self) -> list[KnowledgeItem]:
        """Rehydrate every remembered problem into a :class:`Problem`."""
        result: list[KnowledgeItem] = []
        for key, raw in self._items_by_problem_key.items():
            try:
                # Rehydrate submissions from the separate submission store
                subs = self.submissions_for_problem(key)
                raw_with_subs = dict(raw)
                if subs:
                    raw_with_subs["submissions"] = [s.to_dict() for s in subs]
                result.append(Problem.model_validate(raw_with_subs))
            except Exception:
                # Best-effort: skip corrupted entries rather than crash
                continue
        return result

    def problem_count(self) -> int:
        return len(self._items_by_problem_key)
