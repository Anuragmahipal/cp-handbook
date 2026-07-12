"""The Learning Intermediate Representation (LIR).

``handbook.learning`` is a renderer-independent model of *learning
content*: pages, sections, and the visual/textual/code building blocks
inside them, plus the review and pathing metadata that make a page more
than a static document.

Deliberately excluded, by design constraint: this package contains no
HTML, Markdown, Obsidian, CSS, Canvas, React, SVG, or PDF concepts of
any kind, and it renders nothing. It is the *language* a future family
of renderers (Markdown, an interactive canvas, handwritten-style notes,
flashcards, slides, PDF, ...) would all read from -- unchanged by which
renderer eventually consumes it. No renderer is built here.

It is also deliberately independent of ``handbook.models`` (the CP
domain knowledge model), ``handbook.core``/``handbook.renderers`` (the
Markdown-backed storage and rendering engine), and ``handbook.sync``
(the Codeforces sync pipeline). Nothing in this package imports from
any of those, and nothing in them imports from this. A future bridge
that projects a ``KnowledgeItem`` into a ``Page`` is a natural next
chunk, but it is explicitly not this one -- see
``ARCHITECTURE_NOTES_LEARNING.md`` for the full list of what's
deferred.

Module map
----------
``versioning``   -- the immutable base classes (``LIRModel``,
                     ``Identified``, ``Revisable``) every model in this
                     package builds on, plus the schema-version seam.
``enums``        -- every enumeration used across the representation.
``richtext``     -- ``Span`` / ``RichText``: structured inline text,
                     the renderer-independent alternative to Markdown
                     inline syntax.
``blocks``       -- the content primitives that live inside a
                     ``Section``: ``TextBlock``, ``CodeBlock``,
                     ``VisualBlock``, ``DiagramBlock``, ``Callout``,
                     and the diagram edge types ``Arrow`` /
                     ``Connection``.
``review``       -- ``MemoryAnchor`` (a retrieval cue) and
                     ``ReviewCue`` (its scheduling state).
``page``         -- ``PageMetadata``, ``Section``, ``Page``: the
                     document structure.
``path``         -- ``LearningPath`` / ``PathStep``: cross-page
                     sequencing.
``serialization`` -- explicit, schema-version-aware JSON dump/load for
                     the two independently serializable roots
                     (``Page``, ``LearningPath``).
``examples``     -- one fully worked ``Page``, used by the test suite
                     and as living documentation of the model.
"""

from __future__ import annotations

from handbook.learning.blocks import (
    Arrow,
    Block,
    Callout,
    CodeAnnotation,
    CodeBlock,
    Connection,
    DiagramBlock,
    ElementPosition,
    TextBlock,
    VisualBlock,
)
from handbook.learning.enums import (
    AnchorType,
    CalloutKind,
    ConnectionStyle,
    DiagramKind,
    ElementRole,
    Emphasis,
    LayoutHint,
    ReviewStatus,
    TextRole,
)
from handbook.learning.exceptions import LearningModelError, SchemaVersionError
from handbook.learning.page import Page, PageMetadata, Section
from handbook.learning.path import LearningPath, PathStep
from handbook.learning.review import MemoryAnchor, ReviewCue
from handbook.learning.richtext import RichText, Span
from handbook.learning.serialization import (
    dump_learning_path,
    dump_page,
    load_learning_path,
    load_page,
)
from handbook.learning.versioning import (
    CURRENT_SCHEMA_VERSION,
    Identified,
    LIRModel,
    Revisable,
    supersede,
)

__all__ = [
    # versioning / base classes
    "LIRModel",
    "Identified",
    "Revisable",
    "supersede",
    "CURRENT_SCHEMA_VERSION",
    # rich text
    "Span",
    "RichText",
    # blocks
    "TextBlock",
    "CodeBlock",
    "CodeAnnotation",
    "VisualBlock",
    "ElementPosition",
    "DiagramBlock",
    "Arrow",
    "Connection",
    "Callout",
    "Block",
    # review
    "MemoryAnchor",
    "ReviewCue",
    # page structure
    "PageMetadata",
    "Section",
    "Page",
    # pathing
    "PathStep",
    "LearningPath",
    # enums
    "Emphasis",
    "TextRole",
    "CalloutKind",
    "DiagramKind",
    "LayoutHint",
    "ElementRole",
    "ConnectionStyle",
    "ReviewStatus",
    "AnchorType",
    # errors
    "LearningModelError",
    "SchemaVersionError",
    # serialization
    "dump_page",
    "load_page",
    "dump_learning_path",
    "load_learning_path",
]
