"""``SVGRenderer``: turns one ``DiagramBlock`` into a static, inline
``<svg>`` fragment.

Layout is grid-based, driven by each element's
``ElementPosition(row, col)`` -- elements with no explicit position are
auto-placed on a fresh row below whatever positions were given, in
element order, so a diagram author never has to hand-place every node.
Edges are drawn between grid cells, not between raw pixel coordinates
a caller specified: this module owns the entire coordinate system, and
nothing about it is dragged or interactive -- it is computed once, the
same way every time, from the diagram's data.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from handbook.learning.blocks import Arrow, Connection, DiagramBlock, VisualBlock
from handbook.learning.enums import ConnectionStyle, ElementRole
from handbook.renderers.notebook.theme import NotebookTheme

_CELL_WIDTH = 150
_CELL_HEIGHT = 96
_NODE_WIDTH = 108
_NODE_HEIGHT = 52
_MARKER_HALF = 18
"""Half-extent used for clipping edges into/out of elements that don't
draw a box of their own (POINTER, LABEL) -- keeps an edge from
visually overlapping the marker or text it's pointing at."""
_PADDING = 32


@dataclass(frozen=True, slots=True)
class _Placed:
    element: VisualBlock
    cx: float
    cy: float


def _assign_positions(elements: tuple[VisualBlock, ...]) -> dict[str, _Placed]:
    """Resolve every element's grid cell, auto-placing any that don't
    already have an explicit ``ElementPosition``.

    Auto-placed elements go on one fresh row below every explicitly
    positioned row, left to right in the order they appear -- a simple
    rule, but a deterministic one: the same diagram always produces
    the same layout.
    """
    explicit_rows = [e.position.row for e in elements if e.position is not None]
    auto_row = (max(explicit_rows) + 1) if explicit_rows else 0

    placed: dict[str, _Placed] = {}
    auto_col = 0
    for element in elements:
        if element.position is not None:
            row, col = element.position.row, element.position.col
        else:
            row, col = auto_row, auto_col
            auto_col += 1
        cx = _PADDING + col * _CELL_WIDTH + _NODE_WIDTH / 2
        cy = _PADDING + row * _CELL_HEIGHT + _NODE_HEIGHT / 2
        placed[element.id] = _Placed(element=element, cx=cx, cy=cy)
    return placed


def _half_extent(role: ElementRole) -> tuple[float, float]:
    """The (half-width, half-height) used to clip an edge at this
    element's boundary -- a real box for shapes that draw one, a small
    nominal box for markers/labels that don't."""
    if role in (ElementRole.POINTER, ElementRole.LABEL):
        return (_MARKER_HALF, _MARKER_HALF)
    return (_NODE_WIDTH / 2, _NODE_HEIGHT / 2)


def _clip_to_box(cx: float, cy: float, hw: float, hh: float, tx: float, ty: float):
    """The point where the segment from ``(cx, cy)`` toward ``(tx, ty)``
    crosses the axis-aligned box of half-extents ``(hw, hh)`` centered
    at ``(cx, cy)``."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return (cx, cy)
    candidates = []
    if dx != 0:
        candidates.append(hw / abs(dx))
    if dy != 0:
        candidates.append(hh / abs(dy))
    scale = min(candidates)
    return (cx + dx * scale, cy + dy * scale)


def _edge_path(
    source: _Placed, target: _Placed
) -> tuple[str, tuple[float, float]]:
    """Build the SVG path data for one edge, plus the point its label
    should be centered on.

    Same row or same column -> a straight line. Otherwise -> a
    two-segment orthogonal elbow, horizontal-first or vertical-first
    depending on which axis has the larger gap -- "automatic routing"
    in the sense that no caller ever specifies a path; it is always
    derived from the two endpoints' grid positions.
    """
    shw, shh = _half_extent(source.element.role)
    thw, thh = _half_extent(target.element.role)

    same_row = source.cy == target.cy
    same_col = source.cx == target.cx
    if same_row or same_col:
        start = _clip_to_box(source.cx, source.cy, shw, shh, target.cx, target.cy)
        end = _clip_to_box(target.cx, target.cy, thw, thh, source.cx, source.cy)
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        return (f"M {start[0]:.1f} {start[1]:.1f} L {end[0]:.1f} {end[1]:.1f}", mid)

    horizontal_first = abs(target.cx - source.cx) >= abs(target.cy - source.cy)
    corner = (
        (target.cx, source.cy) if horizontal_first else (source.cx, target.cy)
    )
    start = _clip_to_box(source.cx, source.cy, shw, shh, *corner)
    end = _clip_to_box(target.cx, target.cy, thw, thh, *corner)
    path = (
        f"M {start[0]:.1f} {start[1]:.1f} "
        f"L {corner[0]:.1f} {corner[1]:.1f} "
        f"L {end[0]:.1f} {end[1]:.1f}"
    )
    return (path, corner)


def _dasharray(style: ConnectionStyle) -> str:
    return {
        ConnectionStyle.SOLID: "",
        ConnectionStyle.DASHED: ' stroke-dasharray="8 5"',
        ConnectionStyle.DOTTED: ' stroke-dasharray="2 4"',
    }[style]


class SVGRenderer:
    """Renders one ``DiagramBlock`` to a self-contained ``<svg>`` string."""

    def __init__(self, theme: NotebookTheme) -> None:
        self._theme = theme

    def render(self, diagram: DiagramBlock, *, marker_id: str | None = None) -> str:
        placed = _assign_positions(diagram.elements)
        if marker_id is None:
            # Falls back to the diagram's own id for direct/standalone
            # use of this renderer. NotebookRenderer always passes an
            # explicit marker_id instead (a per-page render counter),
            # because DiagramBlock.id defaults to a random UUID when a
            # caller doesn't pin one -- fine for uniqueness, but it
            # would make two independent renders of "the same" page
            # (same content, freshly constructed, so unset ids come
            # out different each time) produce different SVG output
            # for no content reason. A render-order counter is
            # deterministic for as long as the page's block order is,
            # which is the guarantee this renderer actually needs.
            marker_id = f"arrowhead-{diagram.id}"

        max_x = max((p.cx for p in placed.values()), default=_NODE_WIDTH) + (
            _NODE_WIDTH / 2 + _PADDING
        )
        max_y = max((p.cy for p in placed.values()), default=_NODE_HEIGHT) + (
            _NODE_HEIGHT / 2 + _PADDING
        )

        parts: list[str] = [
            f'<svg viewBox="0 0 {max_x:.0f} {max_y:.0f}" '
            'xmlns="http://www.w3.org/2000/svg" class="lir-diagram" '
            'role="img" aria-label="diagram">',
            self._marker_def(marker_id),
        ]
        for connection in diagram.connections:
            edge_html = self._render_edge(
                connection, placed, marker_id, directed=connection.directed
            )
            parts.append(edge_html)
        for arrow in diagram.arrows:
            parts.append(self._render_edge(arrow, placed, marker_id, directed=True))
        for element in diagram.elements:
            parts.append(self._render_element(placed[element.id]))
        parts.append("</svg>")
        return "\n".join(parts)

    def _marker_def(self, marker_id: str) -> str:
        stroke = self._theme.diagram_edge_stroke
        return (
            "<defs>"
            f'<marker id="{marker_id}" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{stroke}"/>'
            "</marker>"
            "</defs>"
        )

    def _render_edge(
        self,
        edge: Arrow | Connection,
        placed: dict[str, _Placed],
        marker_id: str,
        *,
        directed: bool,
    ) -> str:
        source = placed.get(edge.from_id)
        target = placed.get(edge.to_id)
        if source is None or target is None:  # pragma: no cover - guarded upstream
            return ""
        path, label_point = _edge_path(source, target)
        marker_attr = f' marker-end="url(#{marker_id})"' if directed else ""
        emphasis = getattr(edge, "order", None) is not None
        stroke = (
            self._theme.diagram_emphasis_stroke
            if emphasis
            else self._theme.diagram_edge_stroke
        )
        svg = [
            f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="2"'
            f"{_dasharray(edge.style)}{marker_attr}/>"
        ]
        if edge.label:
            svg.append(self._render_edge_label(edge.label, label_point))
        order = getattr(edge, "order", None)
        if order is not None:
            svg.append(self._render_step_badge(order, source))
        return "".join(svg)

    def _render_edge_label(self, label: str, point: tuple[float, float]) -> str:
        x, y = point
        width = max(24, len(label) * 6.4)
        return (
            f'<rect x="{x - width / 2:.1f}" y="{y - 9:.1f}" width="{width:.1f}" '
            f'height="16" rx="4" fill="{self._theme.card_background}" '
            f'stroke="{self._theme.card_border}"/>'
            f'<text x="{x:.1f}" y="{y + 3:.1f}" text-anchor="middle" '
            f'class="lir-edge-label">{escape(label)}</text>'
        )

    def _render_step_badge(self, order: int, source: _Placed) -> str:
        x, y = source.cx, source.cy - _NODE_HEIGHT / 2 - 10
        return (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" '
            f'fill="{self._theme.accent}"/>'
            f'<text x="{x:.1f}" y="{y + 3:.1f}" text-anchor="middle" '
            f'class="lir-step-badge">{order}</text>'
        )

    def _render_element(self, placed: _Placed) -> str:
        element = placed.element
        role = element.role
        label_text = element.label.as_plain_text()

        if role == ElementRole.LABEL:
            return (
                f'<text x="{placed.cx:.1f}" y="{placed.cy:.1f}" '
                f'text-anchor="middle" class="lir-node-label">'
                f"{escape(label_text)}</text>"
            )

        if role == ElementRole.POINTER:
            return self._render_pointer(placed, label_text)

        return self._render_box(placed, label_text, dashed=role in (
            ElementRole.REGION,
            ElementRole.GROUP,
        ))

    def _render_pointer(self, placed: _Placed, label_text: str) -> str:
        cx, cy = placed.cx, placed.cy
        tip_y = cy - 10
        svg = [
            f'<path d="M {cx - 8:.1f} {tip_y - 10:.1f} L {cx + 8:.1f} '
            f'{tip_y - 10:.1f} L {cx:.1f} {tip_y:.1f} z" '
            f'fill="{self._theme.accent}"/>',
        ]
        if placed.element.value:
            svg.append(
                f'<text x="{cx:.1f}" y="{tip_y - 16:.1f}" text-anchor="middle" '
                f'class="lir-node-value">{escape(placed.element.value)}</text>'
            )
        svg.append(
            f'<text x="{cx:.1f}" y="{cy + 16:.1f}" text-anchor="middle" '
            f'class="lir-node-label">{escape(label_text)}</text>'
        )
        return "".join(svg)

    def _render_box(self, placed: _Placed, label_text: str, *, dashed: bool) -> str:
        cx, cy = placed.cx, placed.cy
        x, y = cx - _NODE_WIDTH / 2, cy - _NODE_HEIGHT / 2
        stroke = (
            self._theme.diagram_emphasis_stroke
            if placed.element.emphasis
            else self._theme.diagram_node_stroke
        )
        stroke_width = 3 if placed.element.emphasis else 1.5
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        value = placed.element.value

        svg = [
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{_NODE_WIDTH}" '
            f'height="{_NODE_HEIGHT}" rx="{self._theme.corner_radius}" '
            f'fill="{self._theme.diagram_node_fill}" stroke="{stroke}" '
            f'stroke-width="{stroke_width}"{dash}/>'
        ]
        if value:
            svg.append(
                f'<text x="{cx:.1f}" y="{cy - 2:.1f}" text-anchor="middle" '
                f'class="lir-node-value">{escape(value)}</text>'
            )
            svg.append(
                f'<text x="{cx:.1f}" y="{cy + 16:.1f}" text-anchor="middle" '
                f'class="lir-node-caption">{escape(label_text)}</text>'
            )
        else:
            svg.append(
                f'<text x="{cx:.1f}" y="{cy + 5:.1f}" text-anchor="middle" '
                f'class="lir-node-label">{escape(label_text)}</text>'
            )
        return "".join(svg)
