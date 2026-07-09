"""Storage engine: the only code in the handbook that touches the filesystem.

StorageEngine owns *where* and *how* rendered content is persisted. It
receives an opaque ``content: str`` plus the metadata needed to place it,
and is responsible for:

  * creating directories
  * generating filenames (via slug)
  * detecting duplicates (by id and by title/slug)
  * atomic, crash-safe writes
  * returning the final stored path

It contains no rendering logic whatsoever -- it never inspects or
understands the *content* it's asked to write. That separation is what
lets future renderers (HTML, JSON, PDF, ...) reuse this engine unchanged.

Duplicate policy
-----------------
Storage makes writes idempotent and predictable using three rules,
checked in this order:

1. **Same id (UUID) as an existing item -> same object.**
   This is treated as an update-in-place: the file is rewritten,
   ``created_at`` is preserved from the first time this id was stored,
   and ``updated_at`` is refreshed. If the title changed since the last
   store (and so the slug/filename changed), the item is relocated and
   its old file is removed -- there is never more than one file per id.

2. **Same title/slug as an existing item, but a different id -> a
   collision.** Two different objects want the same filename.

   * ``overwrite=False`` (the default): the write is rejected with
     :class:`~handbook.exceptions.DuplicateItemError`. Nothing on disk
     is touched.
   * ``overwrite=True``: the existing file is replaced entirely by the
     new item (the old id is forgotten at that path).

3. **No id match, no slug collision -> a brand new item.** It's written
   as-is.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from handbook.core.index import StorageIndex
from handbook.exceptions import DuplicateItemError, StorageError
from handbook.models import KnowledgeItem
from handbook.utils.filesystem import atomic_write, ensure_directory
from handbook.utils.slug import note_slug


@dataclass(frozen=True, slots=True)
class StoragePlan:
    """Where an item will be written and what its persisted metadata is.

    Produced by :meth:`StorageEngine.plan` *before* anything is rendered,
    so the renderer can embed the final, correct ``created_at`` /
    ``updated_at`` values. Handed back to :meth:`StorageEngine.commit`
    once the caller has rendered content for ``item``.
    """

    item: KnowledgeItem
    absolute_path: Path
    relative_path: str
    is_update: bool
    stale_relative_path: str | None = None
    """Old location to delete, if this item moved because its title changed."""


class StorageEngine:
    """Production storage layer for one vault root."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._index = StorageIndex(self.root)

    def plan(
        self,
        item: KnowledgeItem,
        *,
        folder_name: str,
        extension: str,
        overwrite: bool,
    ) -> StoragePlan:
        """Resolve the destination and metadata for ``item`` without writing it.

        Raises:
            StorageError: if a filesystem-safe filename can't be derived
                from the item's title.
            DuplicateItemError: if a different item already owns this
                title's slot and ``overwrite`` is ``False``.
        """
        slug = note_slug(item.title)
        if not slug:
            raise StorageError(
                f"Could not derive a filename from title {item.title!r}: "
                "it produced an empty slug."
            )

        relative_path = f"{folder_name}/{slug}{extension}"
        now = datetime.now()

        existing = self._index.get_by_id(item.id)
        if existing is not None:
            resolved = item.model_copy(
                update={"created_at": existing.created_at, "updated_at": now}
            )
            stale = (
                existing.relative_path
                if existing.relative_path != relative_path
                else None
            )
            return StoragePlan(
                item=resolved,
                absolute_path=self.root / relative_path,
                relative_path=relative_path,
                is_update=True,
                stale_relative_path=stale,
            )

        owner_id = self._index.get_owner(relative_path)
        if owner_id is not None and owner_id != item.id:
            if not overwrite:
                raise DuplicateItemError(
                    f"An item titled {item.title!r} already exists at "
                    f"'{relative_path}'. Pass overwrite=True to replace it, "
                    "or change the title."
                )
            resolved = item.model_copy(update={"updated_at": now})
            return StoragePlan(
                item=resolved,
                absolute_path=self.root / relative_path,
                relative_path=relative_path,
                is_update=True,
            )

        resolved = item.model_copy(update={"updated_at": now})
        return StoragePlan(
            item=resolved,
            absolute_path=self.root / relative_path,
            relative_path=relative_path,
            is_update=False,
        )

    def commit(self, plan: StoragePlan, content: str) -> Path:
        """Write ``content`` to disk according to ``plan`` and update the index.

        Returns the absolute path the content was written to.
        """
        ensure_directory(plan.absolute_path.parent)
        atomic_write(plan.absolute_path, content)

        if plan.stale_relative_path is not None:
            (self.root / plan.stale_relative_path).unlink(missing_ok=True)
            self._index.drop_path(plan.stale_relative_path)

        owner_id = self._index.get_owner(plan.relative_path)
        if owner_id is not None and owner_id != plan.item.id:
            self._index.drop_path(plan.relative_path)

        self._index.upsert(plan.item.id, plan.relative_path, plan.item.created_at)
        return plan.absolute_path
