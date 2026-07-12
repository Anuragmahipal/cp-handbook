"""Enumerations for ``handbook.learning``.

Deliberately a fresh, local set of enums rather than a reuse of
``handbook.models.enums`` -- this package does not depend on the CP
domain model at all (see the package docstring). Every value here
describes *learning-content structure* (what role a piece of text
plays, what kind of diagram this is, how strong a memory is), never a
rendering detail (no font, no color, no pixel size).
"""

from __future__ import annotations

from enum import StrEnum


class Emphasis(StrEnum):
    """A semantic emphasis a span of text carries.

    Semantic, not visual: ``STRONG`` says "this matters more", not
    "make this bold". A Markdown renderer maps ``STRONG`` to
    ``**...**``; a slides renderer might map it to a larger font; a
    handwritten-notes renderer might map it to underlining. That
    mapping is a renderer's job, not this package's.
    """

    STRONG = "strong"
    EMPHASIS = "emphasis"
    INLINE_CODE = "inline_code"
    STRIKETHROUGH = "strikethrough"
    HIGHLIGHT = "highlight"


class TextRole(StrEnum):
    """What a ``TextBlock`` is doing inside its section.

    Lets a renderer treat, say, the core intuition differently from a
    side aside without needing to parse prose to guess -- directly in
    service of the cognitive-load-management principle (chunk
    information, one idea foregrounded at a time) rather than a flat
    wall of undifferentiated paragraphs.
    """

    BODY = "body"
    INTUITION = "intuition"
    EXPLANATION = "explanation"
    SUMMARY = "summary"
    CAPTION = "caption"


class CalloutKind(StrEnum):
    """The nature of an aside called out from the main flow."""

    TIP = "tip"
    WARNING = "warning"
    PITFALL = "pitfall"
    INSIGHT = "insight"
    DEFINITION = "definition"
    EXAMPLE = "example"
    MISTAKE = "mistake"
    QUESTION = "question"


class DiagramKind(StrEnum):
    """The structural family a ``DiagramBlock`` belongs to.

    A hint for layout and interaction, not a rendering instruction --
    a renderer decides *how* to lay out a ``TREE``, this only says
    that it is one.
    """

    TREE = "tree"
    GRAPH = "graph"
    GRID = "grid"
    SEQUENCE = "sequence"
    TIMELINE = "timeline"
    STATE_MACHINE = "state_machine"
    ARRAY = "array"
    OTHER = "other"


class LayoutHint(StrEnum):
    """A coarse hint for how a diagram's elements relate spatially.

    Intentionally abstract (no coordinates, no pixels): a hierarchical
    layout hint lets a canvas renderer lay out a real tree, a
    handwritten-notes renderer indent nested bullets, and a slides
    renderer reveal parent-then-children across builds -- three very
    different concrete layouts from one shared intent.
    """

    HIERARCHICAL = "hierarchical"
    GRID = "grid"
    LINEAR = "linear"
    RADIAL = "radial"
    FREEFORM = "freeform"


class ElementRole(StrEnum):
    """What a single ``VisualBlock`` represents within a diagram (or
    on its own, as a standalone visual annotation in a section)."""

    NODE = "node"
    STATE = "state"
    VALUE = "value"
    POINTER = "pointer"
    REGION = "region"
    GROUP = "group"
    LABEL = "label"


class ConnectionStyle(StrEnum):
    """The semantic weight of an edge between two visual elements.

    Not a line-drawing instruction -- a renderer chooses what "dashed"
    looks like in its medium (an actual dashed line on a canvas, a
    lighter ink stroke in a handwritten-notes renderer, a fainter
    arrow on a slide).
    """

    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class ReviewStatus(StrEnum):
    """Where a ``ReviewCue`` stands in its (externally scheduled) review
    lifecycle. The state machine implied by these values -- when to
    move from one to the next -- belongs to a future review-scheduling
    engine, not to this representation; this only names the states."""

    NEW = "new"
    LEARNING = "learning"
    DUE = "due"
    MASTERED = "mastered"
    SUSPENDED = "suspended"


class AnchorType(StrEnum):
    """The flavor of retrieval cue a ``MemoryAnchor`` offers."""

    KEYWORD = "keyword"
    QUESTION = "question"
    MNEMONIC = "mnemonic"
    PATTERN_NAME = "pattern_name"
    IMAGE_CUE = "image_cue"
