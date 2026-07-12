"""The immutable base classes every model in this package builds on.

Two versioning concepts live in this package, deliberately kept
separate:

``schema_version`` (a field on ``Page`` and ``LearningPath`` only, the
    two independently-serializable roots) describes the *shape* of the
    serialized data itself -- the format ``handbook.learning``
    defines. It exists so a blob of stored JSON is self-describing: a
    future loader can check it before attempting to parse, rather than
    discovering incompatibility as an opaque validation failure deep
    in Pydantic. Bumping it is a package-level event (a breaking
    change to the model), not something that happens per-edit.

``version`` (a field on every :class:`Revisable`: ``Page``,
    ``Section``, ``LearningPath``) is the *content* revision counter --
    it goes up every time a human or an AI agent produces a new
    revision of that specific object. This is the mechanism behind
    "incremental note evolution": revising a ``Section`` never mutates
    it (nothing in this package is mutable) and never silently
    replaces it either. :meth:`Revisable.revise` returns a new object
    with a new id, ``version + 1``, and ``revision_of`` pointing back
    at the original; :func:`supersede` returns a copy of the *original*
    with ``superseded_by`` set. A store that keeps both the flagged
    original and the new revision preserves the full history instead
    of overwriting it -- the "student's own prior understanding being
    corrected is a visible, nameable moment" behavior this
    representation is meant to support.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

CURRENT_SCHEMA_VERSION: Final[int] = 1
"""The schema version this version of ``handbook.learning`` produces
and reads. Bump this, and add a migration seam in
:mod:`handbook.learning.serialization`, the day this package's shape
changes in a way old serialized data can't be read as-is."""


class LIRModel(BaseModel):
    """Root base class for every model in this package.

    ``frozen=True``: nothing in this representation is mutable in
    place. A future canvas renderer, a slide renderer, and a PDF
    renderer can all hold a reference to the same ``Page`` and read it
    concurrently without ever worrying that one of them changes it out
    from under the others. "Editing" a page means producing a new
    ``Page`` (see ``Revisable.revise``), not mutating the existing one.

    ``extra="forbid"``: this package is meant to be a closed,
    intentional vocabulary. Silently accepting unknown fields would
    let renderer-specific data (an HTML class name, an SVG path, a
    pixel offset) leak in through the back door of a permissive
    schema -- exactly what the "renderer independent" constraint rules
    out.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class Identified(LIRModel):
    """Adds a stable id to any model that needs to be independently
    addressable -- referenced by an ``Arrow``'s endpoints, a
    ``MemoryAnchor``'s target, a ``LearningPath`` step, and so on.

    Matches the convention already used by
    ``handbook.models.base.KnowledgeItem``: a random UUID by default,
    but always overridable by a caller (human or AI agent) that
    already knows what id something should have -- e.g. when
    reconstructing a page from stored data.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))


class Revisable(Identified):
    """Adds content-revision tracking to a top-level, independently
    meaningful object: ``Page``, ``Section``, ``LearningPath``.

    Deliberately *not* applied to the small value types nested inside
    a ``Section`` (blocks, arrows, connections) -- those are revised as
    part of revising their owning ``Section``, the same way a sentence
    isn't independently version-controlled from the paragraph it lives
    in.
    """

    version: int = Field(default=1, ge=1)
    revision_of: str | None = None
    """Id of the object this one is a revision of, or ``None`` for an
    original (version 1)."""
    superseded_by: str | None = None
    """Id of the newer revision that replaces this one, or ``None`` if
    this is still the current revision. Set via :func:`supersede`,
    never by :meth:`revise` itself -- see module docstring."""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def revise(self, **changes: object) -> Self:
        """Return a new revision of this object.

        The new object gets a fresh id, ``version`` incremented by
        one, ``revision_of`` pointing back at ``self.id``, both
        timestamps reset to now, and ``superseded_by`` reset to
        ``None`` (a new revision starts out current). Any keyword
        argument overrides that default and is applied on top -- the
        same ``update=`` mechanism as ``BaseModel.model_copy``, which
        this delegates to.

        This method does not, and cannot, mark ``self`` as superseded
        -- ``self`` is frozen. Call :func:`supersede` separately with
        both objects once the new revision has been accepted, so a
        caller that decides *not* to keep the new revision hasn't
        mutated anything.
        """
        overrides: dict[str, object] = {
            "id": str(uuid4()),
            "version": self.version + 1,
            "revision_of": self.id,
            "superseded_by": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        overrides.update(changes)
        return self.model_copy(update=overrides)


def supersede[T: Revisable](original: T, new: Revisable) -> T:
    """Return a copy of ``original`` flagged as superseded by ``new``.

    ``original`` itself is untouched (it's frozen); this returns a new
    object. Callers persist both the returned, flagged copy of the old
    revision and ``new`` -- the pair *is* the history. Typical use::

        revised_section = section.revise(heading=new_heading)
        flagged_section = supersede(section, revised_section)
    """
    return original.model_copy(
        update={"superseded_by": new.id, "updated_at": datetime.now()}
    )
