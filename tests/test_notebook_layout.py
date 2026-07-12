"""Tests for handbook.renderers.notebook.layout."""

from __future__ import annotations

from handbook.learning.blocks import CodeBlock, DiagramBlock, TextBlock
from handbook.learning.page import Section
from handbook.learning.richtext import RichText
from handbook.renderers.notebook.layout import LayoutEngine


def _light_section(name: str) -> Section:
    return Section(
        heading=RichText.plain(name),
        blocks=(TextBlock(content=RichText.plain("short")),),
    )


def _section_with_diagram(name: str) -> Section:
    return Section(
        heading=RichText.plain(name),
        blocks=(DiagramBlock(),),
    )


def _section_with_code(name: str) -> Section:
    return Section(
        heading=RichText.plain(name),
        blocks=(CodeBlock(language="cpp", source="int x = 1;"),),
    )


def test_light_sections_pack_up_to_three_per_row():
    sections = tuple(_light_section(f"S{i}") for i in range(3))
    plan = LayoutEngine().plan(sections)
    assert len(plan.rows) == 1
    assert len(plan.rows[0].sections) == 3


def test_a_fourth_light_section_starts_a_new_row():
    sections = tuple(_light_section(f"S{i}") for i in range(4))
    plan = LayoutEngine().plan(sections)
    assert [len(row.sections) for row in plan.rows] == [3, 1]


def test_a_diagram_section_always_gets_its_own_row():
    sections = (
        _light_section("Before"),
        _section_with_diagram("Diagram"),
        _light_section("After"),
    )
    plan = LayoutEngine().plan(sections)
    headings = [
        [s.heading.as_plain_text() for s in row.sections] for row in plan.rows
    ]
    assert headings == [["Before"], ["Diagram"], ["After"]]


def test_layout_preserves_original_section_order():
    sections = tuple(_light_section(f"S{i}") for i in range(5))
    plan = LayoutEngine().plan(sections)
    flattened = [s.heading.as_plain_text() for row in plan.rows for s in row.sections]
    assert flattened == [f"S{i}" for i in range(5)]


def test_empty_page_produces_no_rows():
    plan = LayoutEngine().plan(())
    assert plan.rows == ()


def test_layout_is_deterministic_across_calls():
    sections = (
        _light_section("A"),
        _section_with_code("B"),
        _light_section("C"),
        _section_with_diagram("D"),
    )
    plan1 = LayoutEngine().plan(sections)
    plan2 = LayoutEngine().plan(sections)
    assert plan1 == plan2
