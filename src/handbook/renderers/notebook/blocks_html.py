"""Block-level and inline HTML rendering.

One function per concept in the representation: rich text, one per
block type, memory anchors, review badges. ``render_block`` is the one
dispatch point a caller needs -- it switches on ``block.block_type``
(the same discriminator Pydantic uses to parse the union) rather than
``isinstance`` chains, so adding a new block kind to the LIR later
means adding one branch here, not restructuring a chain of type
checks.
"""

from __future__ import annotations

from collections.abc import Iterator
from html import escape

from handbook.learning.blocks import (
    Block,
    Callout,
    CodeBlock,
    DiagramBlock,
    TextBlock,
    VisualBlock,
)
from handbook.learning.enums import Emphasis
from handbook.learning.review import MemoryAnchor, ReviewCue
from handbook.learning.richtext import RichText
from handbook.renderers.notebook.svg import SVGRenderer
from handbook.renderers.notebook.syntax import highlight_line

_EMPHASIS_TAGS: dict[Emphasis, str] = {
    Emphasis.STRONG: "strong",
    Emphasis.EMPHASIS: "em",
    Emphasis.INLINE_CODE: "code",
    Emphasis.STRIKETHROUGH: "s",
    Emphasis.HIGHLIGHT: "mark",
}
_EMPHASIS_ORDER = (
    Emphasis.HIGHLIGHT,
    Emphasis.STRIKETHROUGH,
    Emphasis.INLINE_CODE,
    Emphasis.EMPHASIS,
    Emphasis.STRONG,
)
"""Innermost-first nesting order for spans carrying more than one
emphasis, so ``STRONG`` -- the most common case -- ends up as the
outermost, most visually obvious tag."""


def render_rich_text(rich_text: RichText) -> str:
    """Render a ``RichText`` to an inline HTML fragment."""
    pieces: list[str] = []
    for span in rich_text.spans:
        text = escape(span.text)
        for emphasis in _EMPHASIS_ORDER:
            if emphasis in span.emphasis:
                tag = _EMPHASIS_TAGS[emphasis]
                text = f"<{tag}>{text}</{tag}>"
        if span.link_target:
            target = escape(span.link_target)
            text = f'<span class="lir-link" title="{target}">{text}</span>'
        pieces.append(text)
    return "".join(pieces)


def render_text_block(block: TextBlock) -> str:
    return (
        f'<p class="lir-text lir-text-{block.role.value}">'
        f"{render_rich_text(block.content)}</p>"
    )


def render_code_block(block: CodeBlock) -> str:
    annotations_by_line = {a.line: a.note for a in block.annotations}
    lines = block.source.split("\n")
    rows: list[str] = []
    for i, line in enumerate(lines, start=1):
        row_class = "lir-code-row"
        if i in block.highlighted_lines:
            row_class += " lir-code-row-highlighted"
        note = annotations_by_line.get(i, "")
        if note:
            note_cell = f'<td class="lir-code-note">{escape(note)}</td>'
        else:
            note_cell = '<td class="lir-code-note"></td>'
        highlighted = highlight_line(line, block.language)
        rows.append(
            f'<tr class="{row_class}">'
            f'<td class="lir-code-lineno">{i}</td>'
            f'<td class="lir-code-line"><code>{highlighted}</code></td>'
            f"{note_cell}"
            "</tr>"
        )
    caption = (
        f'<figcaption class="lir-code-caption">{escape(block.caption)}</figcaption>'
        if block.caption
        else ""
    )
    return (
        '<figure class="lir-code-block">'
        f"{caption}"
        f'<table class="lir-code" data-language="{escape(block.language)}">'
        f"{''.join(rows)}</table>"
        "</figure>"
    )


def render_visual_chip(block: VisualBlock) -> str:
    """A standalone ``VisualBlock`` (not inside a ``DiagramBlock``): a
    small labeled chip, rendered in plain HTML/CSS rather than SVG --
    there is nothing to connect it to, so it doesn't need a diagram's
    coordinate system.
    """
    emphasis_class = " lir-visual-chip-emphasis" if block.emphasis else ""
    value_html = (
        f'<span class="lir-visual-chip-value">{escape(block.value)}</span>'
        if block.value
        else ""
    )
    return (
        f'<div class="lir-visual-chip lir-role-{block.role.value}{emphasis_class}">'
        f"{value_html}"
        f'<span class="lir-visual-chip-label">{render_rich_text(block.label)}</span>'
        "</div>"
    )


def render_callout(
    callout: Callout,
    svg_renderer: SVGRenderer,
    diagram_counter: Iterator[int] | None = None,
) -> str:
    title_html = (
        f'<div class="lir-callout-title">{escape(callout.title)}</div>'
        if callout.title
        else ""
    )
    body_html = "".join(
        render_block(body_block, svg_renderer, diagram_counter)
        for body_block in callout.body
    )
    return (
        f'<div class="lir-callout lir-callout-{callout.kind.value}">'
        f"{title_html}"
        f'<div class="lir-callout-body">{body_html}</div>'
        "</div>"
    )


def render_memory_anchor(anchor: MemoryAnchor) -> str:
    """A ``MemoryAnchor`` rendered as a small sticky-note-style card:
    the prompt only, deliberately never the answer it points at (see
    the module docstring on ``handbook.learning.review`` for why) --
    this is a retrieval cue, not a restated explanation.
    """
    return (
        f'<div class="lir-anchor" data-anchor-type="{anchor.anchor_type.value}">'
        f'<span class="lir-anchor-kicker">Recall</span>'
        f'<span class="lir-anchor-prompt">{render_rich_text(anchor.prompt)}</span>'
        "</div>"
    )


def render_review_badge(cue: ReviewCue) -> str:
    return (
        f'<span class="lir-review-badge lir-review-{cue.status.value}">'
        f"{cue.status.value.upper()}</span>"
    )


def render_diagram_block(
    block: DiagramBlock, svg_renderer: SVGRenderer, *, marker_id: str
) -> str:
    caption = (
        f'<figcaption class="lir-diagram-caption">{escape(block.caption)}'
        "</figcaption>"
        if block.caption
        else ""
    )
    diagram_svg = svg_renderer.render(block, marker_id=marker_id)
    return f'<figure class="lir-diagram-block">{diagram_svg}{caption}</figure>'


def render_block(
    block: Block,
    svg_renderer: SVGRenderer,
    diagram_counter: Iterator[int] | None = None,
) -> str:
    """Dispatch a single ``Block`` to its renderer, by ``block_type``.

    ``diagram_counter``, when given, supplies a fresh, page-scoped
    index for each ``DiagramBlock`` encountered -- see
    :class:`~handbook.renderers.notebook.svg.SVGRenderer`'s ``render``
    docstring for why that's preferable to using the diagram's own id
    for its SVG marker. When ``None`` (the default, used by callers --
    typically tests -- that only care about one block in isolation),
    :func:`render_diagram_block` falls back to the diagram's own id.
    """
    if block.block_type == "text":
        return render_text_block(block)
    if block.block_type == "code":
        return render_code_block(block)
    if block.block_type == "visual":
        return render_visual_chip(block)
    if block.block_type == "diagram":
        index = next(diagram_counter) if diagram_counter is not None else None
        if index is not None:
            marker_id = f"arrowhead-{index}"
        else:
            marker_id = f"arrowhead-{block.id}"
        return render_diagram_block(block, svg_renderer, marker_id=marker_id)
    if block.block_type == "callout":
        return render_callout(block, svg_renderer, diagram_counter)
    raise ValueError(  # pragma: no cover
        f"Unsupported block_type: {block.block_type!r}"
    )
