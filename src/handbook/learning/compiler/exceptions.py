"""Exception hierarchy for ``handbook.learning.compiler``.

Mirrors the shape of ``handbook.exceptions`` and
``handbook.learning.exceptions``: one root, narrow subclasses for
specific failure kinds. Per-object structural problems (a dangling
reference, a duplicate id) are still raised as ``pydantic.ValidationError``
from inside the LIR models the compiler constructs -- this module only
adds the failure kinds that are specific to *compilation itself*.
"""

from __future__ import annotations


class CompilerError(Exception):
    """Base class for every error raised by ``handbook.learning.compiler``."""


class UnsupportedKnowledgeTypeError(CompilerError):
    """Raised when no :class:`~handbook.learning.compiler.base.Compiler` is
    registered for a given ``KnowledgeItem`` type (or any of its ancestors).

    Deliberately loud rather than silently skipping the item or falling
    back to some generic compiler -- the same "fail clearly, don't guess"
    choice ``handbook.core.folders.resolve_folder`` already makes for an
    unregistered ``KnowledgeItem`` subtype. A caller that wants to
    tolerate unsupported types (e.g. the sync pipeline, which only ever
    sees ``Problem`` today) catches this explicitly rather than the
    registry swallowing it internally.
    """
