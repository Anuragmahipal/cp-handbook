"""Low-level filesystem helpers shared by the storage engine and index."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def ensure_directory(path: Path) -> None:
    """Create ``path`` (and any missing parents) if it doesn't already exist."""
    path.mkdir(parents=True, exist_ok=True)


def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write ``content`` to ``path`` atomically.

    The content is written to a temporary file in the same directory as
    ``path``, then moved into place with :func:`os.replace`. That rename
    is atomic on both POSIX and Windows, so a reader can never observe a
    partially-written file, and a crash mid-write cannot corrupt whatever
    was already at ``path``.
    """
    ensure_directory(path.parent)

    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as tmp_file:
            tmp_file.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
