"""Persists a :class:`~handbook.sync.revision_note.RevisionNote` to disk.

Two files per note, matching the existing "internal bookkeeping vs.
human-visible content" split already used by ``handbook.core.index``
and ``handbook.core.storage``:

* A human-readable Markdown preview, in the vault proper, next to
  Algorithms/Problems/etc. -- for a person to actually look at while
  converting it into a handwritten note.
* The canonical JSON intermediate representation, under the vault's
  ``.handbook/`` directory -- for a future handwriting renderer (or any
  other tool) to consume as data, without re-parsing Markdown.

Uses the *existing* Jinja rendering engine
(:func:`handbook.template_engine.render`) and the *existing* atomic
write helper (:func:`handbook.utils.filesystem.atomic_write`) rather
than inventing new ones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from handbook.sync.revision_note import RevisionNote
from handbook.template_engine import render as render_jinja_template
from handbook.utils.filesystem import atomic_write
from handbook.utils.slug import note_slug

_REVISION_NOTES_FOLDER = "Revision Notes"
_TEMPLATE_NAME = "sync/revision_note.md.j2"
_JSON_SUBDIR = Path(".handbook") / "sync" / "revision_notes"


@dataclass(frozen=True, slots=True)
class WrittenNote:
    """Where one :class:`RevisionNote` ended up on disk."""

    markdown_path: Path
    json_path: Path


def write_revision_note(vault_root: Path, note: RevisionNote) -> WrittenNote:
    """Render and persist ``note``, returning both output paths.

    Idempotent by construction: both paths are derived deterministically
    from the note's problem (its slug and its id), so re-running this
    for the same problem overwrites the same two files rather than
    accumulating duplicates.
    """
    payload = note.model_dump(mode="json")

    slug = note_slug(note.problem_title) or note.problem_id
    markdown_path = vault_root / _REVISION_NOTES_FOLDER / f"{slug}.md"
    json_path = vault_root / _JSON_SUBDIR / f"{note.problem_id}.json"

    markdown = render_jinja_template(_TEMPLATE_NAME, **payload)
    atomic_write(markdown_path, markdown)
    atomic_write(json_path, json.dumps(payload, indent=2, ensure_ascii=False))

    return WrittenNote(markdown_path=markdown_path, json_path=json_path)
