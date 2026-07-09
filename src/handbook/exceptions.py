"""Exception hierarchy for the handbook persistence engine.

Every error raised by ``handbook.core`` or ``handbook.handbook`` is a
subclass of :class:`HandbookError`, so callers can catch broadly with
``except HandbookError`` or narrowly with a specific subclass.
"""

from __future__ import annotations


class HandbookError(Exception):
    """Base class for every handbook-specific error."""


class ConfigurationError(HandbookError):
    """Raised when the handbook is misconfigured (e.g. an unusable vault path)."""


class InvalidItemError(HandbookError):
    """Raised when :meth:`Handbook.store` is called with a non-``KnowledgeItem``."""


class StorageError(HandbookError):
    """Raised for storage-layer failures: unresolvable folders, unwritable
    slugs, filesystem problems, and similar."""


class DuplicateItemError(StorageError):
    """Raised when a different item would silently overwrite an existing
    one and the caller has not opted in via ``overwrite=True``."""


class RenderError(HandbookError):
    """Raised when a renderer cannot produce output for a given item."""
