"""Storage index: tracks id <-> path relationships for a vault.

This is what lets :class:`~handbook.core.storage.StorageEngine` answer
"have I seen this UUID before?" and "is this filename already taken?" in
O(1), without ever reading or understanding rendered content. That
independence from content format is what keeps storage reusable for
future Markdown/HTML/JSON/PDF renderers alike.

Persisted as plain JSON at ``<vault_root>/.handbook/index.json``. This
file is internal bookkeeping -- callers should never need to read or
edit it by hand.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from handbook.utils.filesystem import atomic_write

_INDEX_DIRNAME = ".handbook"
_INDEX_FILENAME = "index.json"


@dataclass(frozen=True, slots=True)
class IndexRecord:
    """A single tracked item inside the storage index."""

    item_id: str
    relative_path: str
    created_at: datetime


class StorageIndex:
    """Bidirectional id <-> path lookup, persisted as JSON."""

    def __init__(self, vault_root: Path):
        self._index_path = vault_root / _INDEX_DIRNAME / _INDEX_FILENAME
        self._by_id: dict[str, dict[str, str]] = {}
        self._by_path: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self._index_path.exists():
            return
        raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        self._by_id = raw.get("records", {})
        self._by_path = raw.get("paths", {})

    def _save(self) -> None:
        payload = {"version": 1, "records": self._by_id, "paths": self._by_path}
        atomic_write(
            self._index_path, json.dumps(payload, indent=2, ensure_ascii=False)
        )

    def get_by_id(self, item_id: str) -> IndexRecord | None:
        """Return the record for ``item_id``, or ``None`` if it's unknown."""
        record = self._by_id.get(item_id)
        if record is None:
            return None
        return IndexRecord(
            item_id=item_id,
            relative_path=record["path"],
            created_at=datetime.fromisoformat(record["created_at"]),
        )

    def get_owner(self, relative_path: str) -> str | None:
        """Return the item id currently occupying ``relative_path``, if any."""
        return self._by_path.get(relative_path)

    def upsert(self, item_id: str, relative_path: str, created_at: datetime) -> None:
        """Record that ``item_id`` now lives at ``relative_path``.

        If ``item_id`` previously lived at a different path, that stale
        path mapping is dropped so the index never points at two
        locations for one id.
        """
        previous = self._by_id.get(item_id)
        if previous is not None and previous["path"] != relative_path:
            self._by_path.pop(previous["path"], None)

        self._by_id[item_id] = {
            "path": relative_path,
            "created_at": created_at.isoformat(),
        }
        self._by_path[relative_path] = item_id
        self._save()

    def drop_path(self, relative_path: str) -> None:
        """Forget whatever item currently occupies ``relative_path``.

        Used when an ``overwrite=True`` write hands a path from one item
        to another, or when a renamed item vacates its old location.
        """
        owner_id = self._by_path.pop(relative_path, None)
        owned_path = self._by_id.get(owner_id, {}).get("path")
        if owner_id is not None and owned_path == relative_path:
            self._by_id.pop(owner_id, None)
        self._save()
