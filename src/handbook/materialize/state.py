"""MaterializeState: which knowledge items the Materialization Engine
has already created in this vault.

Mirrors :class:`handbook.sync.state.SyncState` deliberately closely --
same problem, same shape of solution. There is no vault loader (parsing
a ``KnowledgeItem`` back out of its rendered Markdown) yet -- see
``docs/DEVELOPER_NOTES_SYNC.md`` -- so the only way for
:class:`~handbook.materialize.engine.MaterializationEngine` to know
"have I already materialized an Algorithm called Binary Search", and to
hand a full ``KnowledgeItem`` for it back into this run's graph without
re-reading (or, worse, re-writing and silently clobbering) its on-disk
note, is to keep its own record of what it created. Same tradeoff,
same fix, same file-per-vault convention -- just keyed by slug instead
of by Codeforces problem key.
"""

from __future__ import annotations

import json
from pathlib import Path

from handbook.models import Algorithm, Contest, Mistake, Pattern
from handbook.models.base import KnowledgeItem
from handbook.utils.filesystem import atomic_write

_STATE_RELATIVE_PATH = Path(".handbook") / "materialize" / "state.json"

_MODEL_BY_KIND: dict[str, type[KnowledgeItem]] = {
    Algorithm.KIND: Algorithm,
    Pattern.KIND: Pattern,
    Mistake.KIND: Mistake,
    Contest.KIND: Contest,
}


class MaterializeState:
    """One vault's record of every KnowledgeItem the Materialization
    Engine has ever created, keyed by the item's canonical slug.
    Persisted as plain JSON at
    ``<vault_root>/.handbook/materialize/state.json``.
    """

    def __init__(self, vault_root: Path) -> None:
        self._path = vault_root / _STATE_RELATIVE_PATH
        self._items_by_slug: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._items_by_slug = raw.get("items", {})

    def save(self) -> None:
        payload = {"version": 1, "items": self._items_by_slug}
        atomic_write(self._path, json.dumps(payload, indent=2, ensure_ascii=False))

    def has(self, slug: str) -> bool:
        """Has a knowledge item already been materialized at this slug?"""
        return slug in self._items_by_slug

    def get(self, slug: str) -> KnowledgeItem | None:
        """Reconstruct the previously-materialized item at ``slug``, if any.

        Reloaded from this state file, not from the vault's rendered
        Markdown -- see the module docstring on why. ``None`` if
        nothing has ever been materialized at this slug.
        """
        data = self._items_by_slug.get(slug)
        if data is None:
            return None
        model = _MODEL_BY_KIND[data["kind"]]
        return model.model_validate(data)

    def remember(self, slug: str, item: KnowledgeItem) -> None:
        """Record ``item`` as this vault's materialized item for ``slug``."""
        self._items_by_slug[slug] = item.model_dump(mode="json")

    def known_slugs(self) -> list[str]:
        return list(self._items_by_slug)

    def known_items(self) -> list[KnowledgeItem]:
        """Every previously-materialized item, reconstructed for a full
        graph rebuild -- the same role
        :meth:`handbook.sync.state.SyncState.known_items` plays for
        ``Problem``.
        """
        return [self.get(slug) for slug in self._items_by_slug]  # type: ignore[misc]
