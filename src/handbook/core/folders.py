"""Folder resolution: mapping knowledge types to vault subdirectories.

The caller never chooses where an item is stored. This module is the
single source of truth for that decision, so adding a new knowledge type
only ever requires one new registry entry here.
"""

from __future__ import annotations

from handbook.exceptions import StorageError
from handbook.models import (
    Algorithm,
    Contest,
    KnowledgeItem,
    Mistake,
    Pattern,
    Problem,
    Topic,
)

# Registry of knowledge type -> vault-relative folder name.
# Keyed by exact class; resolve_folder() walks the MRO so subclasses of a
# registered type are resolved automatically.
_FOLDER_MAP: dict[type[KnowledgeItem], str] = {
    Algorithm: "Algorithms",
    Problem: "Problems",
    Pattern: "Patterns",
    Mistake: "Mistakes",
    Contest: "Contests",
    Topic: "Topics",
}


def resolve_folder(item: KnowledgeItem) -> str:
    """Return the vault-relative folder name ``item`` belongs in.

    Raises:
        StorageError: if no folder has been registered for this type (or
            any of its ancestors).
    """
    for klass in type(item).__mro__:
        folder = _FOLDER_MAP.get(klass)
        if folder is not None:
            return folder

    raise StorageError(
        f"No folder mapping registered for type {type(item).__name__!r}. "
        "Register it in handbook.core.folders._FOLDER_MAP."
    )
