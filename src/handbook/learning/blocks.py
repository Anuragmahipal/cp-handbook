"""The content primitives that live inside a :class:`~handbook.learning.page.Section`.

Five block kinds -- :class:`TextBlock`, :class:`CodeBlock`,
:class:`VisualBlock`, :class:`DiagramBlock`, :class:`Callout` -- form
the :data:`Block` discriminated union a ``Section`` is built from.
:class:`Arrow` and :class:`Connection` are not blocks themselves; they
are the typed edges that make a :class:`DiagramBlock` more than an
unordered pile of visual elements.

**Why ``VisualBlock`` is both a block and a diagram element.** A
``VisualBlock`` can appear directly in a ``Section.blocks`` list (one
standalone visual annotation -- a single highlighted state, a lone
labeled value) or inside a ``DiagramBlock.elements`` list (one node
among many, connected to the others by ``Arrow``/``Connection``). It's
the same object either way: "a single visual thing with a role and an
optional value" doesn't change meaning depending on whether it has
neighbors. This reuse is deliberate, not an accident of the object
list this package was asked to build.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from handbook.learning.enums import (
    CalloutKind,
    ConnectionStyle,
    DiagramKind,
    ElementRole,
    LayoutHint,
    TextRole,
)
from handbook.learning.richtext import RichText
from handbook.learning.versioning import Identified, LIRModel

# -- text ---------------------------------------------------------------


class TextBlock(Identified):
    """A run of prose."""

    block_type: Literal["text"] = "text"
    content: RichText
    role: TextRole = TextRole.BODY


# -- code -----------------------------------------------------------------


class CodeAnnotation(LIRModel):
    """A note attached to one line of a :class:`CodeBlock`.

    Deliberately line-addressed rather than embedded in the source
    itself (no inline comments injected into ``CodeBlock.source``):
    the code stays exactly what would compile/run, and the pedagogy
    ("this is why line 7 matters") is carried as structured data a
    renderer can show however fits its medium -- a margin note, a
    tooltip, a separate annotated callout on a slide.
    """

    line: int = Field(ge=1)
    note: str


class CodeBlock(Identified):
    """A block of source code."""

    block_type: Literal["code"] = "code"
    language: str
    """A semantic language identifier, e.g. ``"cpp"``, ``"python"`` --
    not a Markdown fence tag, even though it may look identical."""
    source: str
    caption: str = ""
    highlighted_lines: tuple[int, ...] = ()
    """1-indexed line numbers a renderer may choose to emphasize."""
    annotations: tuple[CodeAnnotation, ...] = ()

    @model_validator(mode="after")
    def _annotations_reference_real_lines(self) -> CodeBlock:
        line_count = self.source.count("\n") + 1 if self.source else 0
        for annotation in self.annotations:
            if annotation.line > line_count:
                raise ValueError(
                    f"CodeAnnotation.line={annotation.line} is beyond "
                    f"the source's {line_count} line(s)"
                )
        return self


# -- visual / diagram -------------------------------------------------------


class ElementPosition(LIRModel):
    """An abstract logical position for a :class:`VisualBlock`.

    Row/column on an implicit grid, not x/y pixels -- a renderer maps
    this to whatever coordinate system its medium actually uses (an
    interactive canvas computes real pixel placement from it; a
    handwritten-notes renderer might turn it into "top row, second
    from the left" prose; a slide renderer might ignore it entirely
    and reveal elements one at a time instead).
    """

    row: int
    col: int


class VisualBlock(Identified):
    """A single visual element: a node, a labeled value, a pointer, a
    highlighted region -- either standalone or as one member of a
    :class:`DiagramBlock`. See the module docstring for why this one
    type serves both roles.
    """

    block_type: Literal["visual"] = "visual"
    role: ElementRole = ElementRole.NODE
    label: RichText
    value: str | None = None
    """What this element currently holds/shows, e.g. an array cell's
    value or a state's name -- distinct from ``label``, which is what
    the element is *called* rather than what it currently *contains*."""
    emphasis: bool = False
    """Marks this as the element to focus on right now. Supports a
    step-through canvas renderer highlighting the active node, or a
    slide renderer choosing what to reveal on the current build step."""
    position: ElementPosition | None = None
    group: str | None = None
    """An optional grouping key (e.g. ``"visited"``, ``"left subtree"``)
    a renderer may use to cluster or color-code related elements."""


class Arrow(Identified):
    """A directed, typically transient edge representing *flow*: a
    pointer moving, a recursive call being made, a state transition
    firing. Distinct from :class:`Connection`, which represents static
    structure rather than movement -- see its docstring.
    """

    from_id: str
    to_id: str
    label: str = ""
    style: ConnectionStyle = ConnectionStyle.SOLID
    order: int | None = None
    """An optional step index. When several arrows describe a
    sequence of moves (not all at once), this lets a step-through
    canvas renderer or a slide-build renderer sequence them instead of
    showing every arrow simultaneously."""


class Connection(Identified):
    """A structural edge between two visual elements: adjacency,
    grouping, equivalence -- a static relationship, not a movement.
    Use :class:`Arrow` instead when the edge represents something
    happening (a call, a transition, a pointer moving); use
    ``Connection`` when it represents something simply *being true*
    (these two cells are adjacent, these two nodes are the same
    component).
    """

    from_id: str
    to_id: str
    label: str = ""
    style: ConnectionStyle = ConnectionStyle.SOLID
    directed: bool = False


class DiagramBlock(Identified):
    """A composed diagram: a set of :class:`VisualBlock` elements
    joined by :class:`Arrow` and/or :class:`Connection` edges.
    """

    block_type: Literal["diagram"] = "diagram"
    kind: DiagramKind = DiagramKind.OTHER
    caption: str = ""
    layout_hint: LayoutHint = LayoutHint.FREEFORM
    elements: tuple[VisualBlock, ...] = ()
    arrows: tuple[Arrow, ...] = ()
    connections: tuple[Connection, ...] = ()

    @model_validator(mode="after")
    def _edges_reference_known_elements(self) -> DiagramBlock:
        known_ids = {element.id for element in self.elements}
        for edge, edge_kind in (
            *((a, "Arrow") for a in self.arrows),
            *((c, "Connection") for c in self.connections),
        ):
            endpoints = ((edge.from_id, "from_id"), (edge.to_id, "to_id"))
            for endpoint, end_name in endpoints:
                if endpoint not in known_ids:
                    raise ValueError(
                        f"{edge_kind}.{end_name}={endpoint!r} does not match "
                        f"any element id in this DiagramBlock"
                    )
        return self


# -- callout ----------------------------------------------------------------

CalloutBody = Annotated[TextBlock | CodeBlock, Field(discriminator="block_type")]


class Callout(Identified):
    """A short aside called out from the main flow: a tip, a pitfall, a
    definition. Its body is a small, finite sequence of text/code
    blocks -- deliberately not the full recursive ``Block`` union, so a
    callout can't nest a diagram inside a callout inside a diagram
    without limit.
    """

    block_type: Literal["callout"] = "callout"
    kind: CalloutKind = CalloutKind.TIP
    title: str = ""
    body: tuple[CalloutBody, ...] = ()


# -- the block union ----------------------------------------------------

Block = Annotated[
    TextBlock | CodeBlock | VisualBlock | DiagramBlock | Callout,
    Field(discriminator="block_type"),
]
"""Every concrete kind of content a ``Section`` can hold, one entry in
reading order. Discriminated on the literal ``block_type`` field each
member carries, so a plain dict/JSON payload round-trips to the
correct concrete class without a caller needing to specify it."""
