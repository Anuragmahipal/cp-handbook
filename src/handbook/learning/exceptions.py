"""Exception hierarchy for ``handbook.learning``.

Mirrors the shape of ``handbook.exceptions``: one root, narrow
subclasses for specific failure kinds. Structural problems with a
single object (a dangling reference, a blank required field, an
unknown id) are raised as plain ``ValueError`` from inside Pydantic
validators -- Pydantic wraps those into ``pydantic.ValidationError``
automatically, which is the existing convention in
``handbook.models.base``. The exceptions here are for failures that
happen *outside* Pydantic's validation machinery, in the plain
functions of :mod:`handbook.learning.serialization`.
"""

from __future__ import annotations


class LearningModelError(Exception):
    """Base class for every error raised by ``handbook.learning``."""


class SchemaVersionError(LearningModelError):
    """Raised when serialized data declares a schema version this
    version of the package does not know how to read.

    Deliberately narrow: this package defines the seam (a
    ``schema_version`` field on every serialization root, checked on
    load) but does not implement migrations between versions -- see
    ``ARCHITECTURE_NOTES_LEARNING.md`` for why that's future work.
    """
