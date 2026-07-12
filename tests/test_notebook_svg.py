"""Tests for handbook.renderers.notebook.svg."""

from __future__ import annotations

from handbook.learning.blocks import Arrow, Connection, DiagramBlock, VisualBlock
from handbook.learning.enums import ConnectionStyle, ElementRole
from handbook.learning.richtext import RichText
from handbook.renderers.notebook.svg import SVGRenderer
from handbook.renderers.notebook.theme import NotebookTheme


def _renderer() -> SVGRenderer:
    return SVGRenderer(NotebookTheme.light_notebook())


def test_renders_a_valid_svg_root():
    node = VisualBlock(id="a", role=ElementRole.NODE, label=RichText.plain("A"))
    diagram = DiagramBlock(elements=(node,))
    svg = _renderer().render(diagram)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg


def test_elements_without_position_are_auto_placed_without_error():
    a = VisualBlock(id="a", role=ElementRole.NODE, label=RichText.plain("A"))
    b = VisualBlock(id="b", role=ElementRole.NODE, label=RichText.plain("B"))
    diagram = DiagramBlock(elements=(a, b), arrows=(Arrow(from_id="a", to_id="b"),))
    svg = _renderer().render(diagram)
    assert svg.count("<rect") == 2


def test_arrow_gets_a_marker_end_and_connection_does_not_unless_directed():
    a = VisualBlock(id="a", role=ElementRole.NODE, label=RichText.plain("A"))
    b = VisualBlock(id="b", role=ElementRole.NODE, label=RichText.plain("B"))
    diagram = DiagramBlock(
        elements=(a, b),
        arrows=(Arrow(from_id="a", to_id="b"),),
        connections=(Connection(from_id="a", to_id="b", directed=False),),
    )
    svg = _renderer().render(diagram)
    assert svg.count("marker-end") == 1  # only the Arrow, not the undirected Connection


def test_directed_connection_also_gets_a_marker():
    a = VisualBlock(id="a", role=ElementRole.NODE, label=RichText.plain("A"))
    b = VisualBlock(id="b", role=ElementRole.NODE, label=RichText.plain("B"))
    diagram = DiagramBlock(
        elements=(a, b),
        connections=(Connection(from_id="a", to_id="b", directed=True),),
    )
    svg = _renderer().render(diagram)
    assert "marker-end" in svg


def test_dashed_and_dotted_edges_get_a_dasharray():
    a = VisualBlock(id="a", role=ElementRole.NODE, label=RichText.plain("A"))
    b = VisualBlock(id="b", role=ElementRole.NODE, label=RichText.plain("B"))
    diagram = DiagramBlock(
        elements=(a, b),
        connections=(
            Connection(from_id="a", to_id="b", style=ConnectionStyle.DASHED),
        ),
    )
    svg = _renderer().render(diagram)
    assert "stroke-dasharray" in svg


def test_ordered_arrows_get_a_step_badge():
    a = VisualBlock(id="a", role=ElementRole.NODE, label=RichText.plain("A"))
    b = VisualBlock(id="b", role=ElementRole.NODE, label=RichText.plain("B"))
    diagram = DiagramBlock(
        elements=(a, b), arrows=(Arrow(from_id="a", to_id="b", order=1),)
    )
    svg = _renderer().render(diagram)
    assert "lir-step-badge" in svg
    assert "<circle" in svg


def test_edge_label_is_rendered_when_present():
    a = VisualBlock(id="a", role=ElementRole.NODE, label=RichText.plain("A"))
    b = VisualBlock(id="b", role=ElementRole.NODE, label=RichText.plain("B"))
    diagram = DiagramBlock(
        elements=(a, b), arrows=(Arrow(from_id="a", to_id="b", label="calls"),)
    )
    svg = _renderer().render(diagram)
    assert "calls" in svg


def test_empty_diagram_renders_without_crashing():
    svg = _renderer().render(DiagramBlock())
    assert svg.startswith("<svg")


def test_svg_render_is_deterministic():
    diagram = DiagramBlock(
        elements=(
            VisualBlock(id="a", role=ElementRole.NODE, label=RichText.plain("A")),
            VisualBlock(id="b", role=ElementRole.NODE, label=RichText.plain("B")),
        ),
        arrows=(Arrow(from_id="a", to_id="b"),),
    )
    renderer = _renderer()
    assert renderer.render(diagram) == renderer.render(diagram)
