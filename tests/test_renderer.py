"""Tests for MarkdownRenderer."""

from __future__ import annotations

from handbook.models import Mistake, Pattern, Problem
from handbook.renderers.markdown_renderer import MarkdownRenderer


def test_extension_is_markdown():
    assert MarkdownRenderer().extension == ".md"


def test_algorithm_uses_dedicated_template():
    from handbook.models import Algorithm

    content = MarkdownRenderer().render(Algorithm(title="Binary Search"))

    assert "Binary Search" in content
    assert "# 🧠 Intuition" in content  # comes from algorithm.md.j2


def test_types_without_a_template_use_generic_fallback():
    content = MarkdownRenderer().render(Pattern(title="Two Pointers"))

    assert content.startswith("---\n")
    assert "title: Two Pointers" in content
    assert "# Two Pointers" in content


def test_generic_fallback_covers_every_current_knowledge_type():
    renderer = MarkdownRenderer()

    for item in (
        Problem(title="A", platform="CF", contest="1", index="A"),
        Pattern(title="B"),
        Mistake(title="C"),
    ):
        content = renderer.render(item)
        assert "---" in content
        assert item.title in content
