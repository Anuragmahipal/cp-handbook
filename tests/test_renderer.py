"""Tests for MarkdownRenderer."""

from __future__ import annotations

from handbook.models import Contest, KnowledgeItem, Mistake, Pattern, Problem, Topic
from handbook.renderers.markdown_renderer import MarkdownRenderer


def test_extension_is_markdown():
    assert MarkdownRenderer().extension == ".md"


def test_algorithm_uses_dedicated_template():
    from handbook.models import Algorithm

    content = MarkdownRenderer().render(Algorithm(title="Binary Search"))

    assert "Binary Search" in content
    assert "# 🧠 Intuition" in content  # comes from algorithm.md.j2


def test_problem_uses_dedicated_template():
    content = MarkdownRenderer().render(
        Problem(title="Two Sum", platform="LeetCode", contest="Easy", index="1")
    )

    assert "Two Sum" in content
    assert "# 🧩 Approach" in content  # comes from problem.md.j2
    assert 'platform: "LeetCode"' in content


def test_pattern_uses_dedicated_template():
    content = MarkdownRenderer().render(Pattern(title="Two Pointers"))

    assert "Two Pointers" in content
    assert "# 🔍 Recognition" in content  # comes from pattern.md.j2


def test_mistake_uses_dedicated_template():
    content = MarkdownRenderer().render(Mistake(title="Off by one"))

    assert "Off by one" in content
    assert "# ⚠️ What Happened" in content  # comes from mistake.md.j2


def test_contest_uses_dedicated_template():
    content = MarkdownRenderer().render(Contest(title="Div 2 Round 999", platform="CF"))

    assert "Div 2 Round 999" in content
    assert "# 📋 Problems" in content  # comes from contest.md.j2


def test_topic_uses_dedicated_template():
    content = MarkdownRenderer().render(Topic(title="Graph Theory"))

    assert "Graph Theory" in content
    assert "# 🗺️" in content  # comes from topic.md.j2


def test_types_without_a_template_use_generic_fallback():
    """Every current knowledge type now has a dedicated template, so this
    exercises the fallback path directly with an ad-hoc, unregistered
    subclass -- the same technique test_folders.py uses to test
    resolve_folder()'s failure path.
    """

    class Unregistered(KnowledgeItem):
        pass

    content = MarkdownRenderer().render(Unregistered(title="Two Pointers"))

    assert content.startswith("---\n")
    assert "title: Two Pointers" in content
    assert "# Two Pointers" in content


def test_generic_fallback_is_valid_for_any_knowledge_item():
    """The generic fallback still has to work for any KnowledgeItem,
    dedicated template or not -- Handbook.store() never checks first."""

    class AnotherUnregistered(KnowledgeItem):
        pass

    renderer = MarkdownRenderer()

    for item in (
        AnotherUnregistered(title="A"),
        AnotherUnregistered(title="B"),
    ):
        content = renderer.render(item)
        assert "---" in content
        assert item.title in content
