"""End-to-end tests for handbook.renderers.notebook.renderer."""

from __future__ import annotations

import re

from handbook.learning.examples import build_example_page
from handbook.learning.path import LearningPath, PathStep
from handbook.learning.serialization import dump_page, load_page
from handbook.renderers.notebook import NotebookRenderer, NotebookTheme

_TAG_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9]*)(?:\s[^>]*?)?(?<!/)>")
_CLOSE_TAG_RE = re.compile(r"</([a-zA-Z][a-zA-Z0-9]*)>")
_VOID_TAGS = {"meta", "br", "img", "link", "hr", "!doctype"}


def _tags_are_balanced(html: str) -> bool:
    from collections import Counter

    opens = Counter(
        t.lower() for t in _TAG_RE.findall(html) if t.lower() not in _VOID_TAGS
    )
    closes = Counter(t.lower() for t in _CLOSE_TAG_RE.findall(html))
    return opens == closes


def test_render_produces_a_complete_standalone_document():
    page = build_example_page()
    result = NotebookRenderer().render(page)
    assert result.html.startswith("<!doctype html>")
    assert "<style>" in result.html
    assert "</html>" in result.html
    assert _tags_are_balanced(result.html)


def test_render_contains_no_javascript():
    page = build_example_page()
    result = NotebookRenderer().render(page)
    assert "<script" not in result.html.lower()
    assert "onclick" not in result.html.lower()


def test_render_embeds_every_diagram_as_inline_svg():
    page = build_example_page()
    result = NotebookRenderer().render(page)
    assert result.html.count("<svg") == 1  # the example page has one DiagramBlock


def test_render_is_idempotent_on_the_same_object():
    page = build_example_page()
    renderer = NotebookRenderer()
    assert renderer.render(page).html == renderer.render(page).html


def test_render_is_deterministic_across_equal_but_distinct_objects():
    page = build_example_page()
    reloaded = load_page(dump_page(page))
    assert reloaded is not page
    renderer = NotebookRenderer()
    assert renderer.render(page).html == renderer.render(reloaded).html


def test_render_differs_by_theme():
    page = build_example_page()
    light = NotebookRenderer(theme=NotebookTheme.light_notebook()).render(page)
    dark = NotebookRenderer(theme=NotebookTheme.dark_notebook()).render(page)
    assert light.html != dark.html


def test_render_includes_memory_anchors_and_review_badges():
    page = build_example_page()
    result = NotebookRenderer().render(page)
    assert "lir-anchor" in result.html
    assert "lir-review-badge" in result.html


def test_render_with_learning_path_highlights_current_step():
    page = build_example_page()
    path = LearningPath(
        title="Search Track",
        steps=(
            PathStep(page_id=page.id, rationale="start"),
            PathStep(page_id="some-other-page"),
        ),
    )
    result = NotebookRenderer().render(page, learning_path=path)
    assert "lir-path-step-current" in result.html
    assert "Search Track" in result.html


def test_render_learning_path_standalone():
    path = LearningPath(
        title="Graphs From Scratch",
        description="A guided sequence through graph algorithms.",
        steps=(
            PathStep(page_id="p1", rationale="Start with BFS/DFS"),
            PathStep(page_id="p2", section_id="s1", optional=True),
        ),
    )
    result = NotebookRenderer().render_learning_path(path)
    assert "Graphs From Scratch" in result.html
    assert "p1" in result.html
    assert "lir-path-optional" in result.html
    assert _tags_are_balanced(result.html)


def test_write_creates_output_html(tmp_path):
    page = build_example_page()
    result = NotebookRenderer().render(page)
    written = result.write(tmp_path)
    assert written.name == "output.html"
    assert written.read_text(encoding="utf-8") == result.html
