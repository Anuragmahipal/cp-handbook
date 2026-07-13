"""Tests for MistakeCompiler, independent of every other compiler."""

from __future__ import annotations

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.learning.enums import CalloutKind
from handbook.models import Algorithm, Mistake, MistakeCategory, Platform, Problem


def _headings(page) -> list[str]:
    return [s.heading.as_plain_text() for s in page.sections]


def test_minimal_mistake_always_gets_what_happened():
    mistake = Mistake(title="Bare Mistake")
    graph = GraphBuilder([mistake]).build()
    result = KnowledgeCompiler(graph).compile(mistake)

    assert _headings(result.page) == ["What Happened"]
    assert any("templated fallback" in w for w in result.warnings)


def test_what_happened_falls_back_to_category_and_occurrences():
    mistake = Mistake(title="X", category=MistakeCategory.OFF_BY_ONE, occurrences=3)
    graph = GraphBuilder([mistake]).build()
    result = KnowledgeCompiler(graph).compile(mistake)

    text = result.page.sections[0].blocks[0].content.as_plain_text()
    assert "Off By One" in text
    assert "3 times" in text


def test_what_happened_prefers_notes_when_present():
    mistake = Mistake(title="X", notes="Submission timed out unexpectedly.")
    graph = GraphBuilder([mistake]).build()
    result = KnowledgeCompiler(graph).compile(mistake)

    text = result.page.sections[0].blocks[0].content.as_plain_text()
    assert text == "Submission timed out unexpectedly."


def test_cause_and_prevention_become_callouts():
    mistake = Mistake(
        title="X",
        cause="hi = mid instead of mid - 1",
        prevention="Trace the two-element case by hand.",
    )
    graph = GraphBuilder([mistake]).build()
    result = KnowledgeCompiler(graph).compile(mistake)

    assert _headings(result.page) == ["What Happened", "Root Cause", "Prevention"]
    root_cause = result.page.sections[1].blocks[0]
    prevention = result.page.sections[2].blocks[0]
    assert root_cause.kind == CalloutKind.PITFALL
    assert prevention.kind == CalloutKind.TIP


def test_memory_anchor_prefers_prevention_over_root_cause_and_what_happened():
    mistake = Mistake(title="X", cause="cause", prevention="prevention")
    graph = GraphBuilder([mistake]).build()
    result = KnowledgeCompiler(graph).compile(mistake)

    prevention_section = result.page.sections[2]
    assert prevention_section.heading.as_plain_text() == "Prevention"
    assert len(prevention_section.memory_anchors) == 1
    assert result.page.sections[0].memory_anchors == ()
    assert result.page.sections[1].memory_anchors == ()


def test_memory_anchor_falls_back_to_what_happened_when_nothing_else_present():
    mistake = Mistake(title="X")
    graph = GraphBuilder([mistake]).build()
    result = KnowledgeCompiler(graph).compile(mistake)

    assert len(result.page.sections[0].memory_anchors) == 1


def test_related_problems_and_algorithms_from_graph():
    mistake = Mistake(
        title="Off by one",
        related_problems=["Binary Search Problem"],
        related_algorithms=["Binary Search"],
    )
    problem = Problem(
        title="Binary Search Problem", platform=Platform.CODEFORCES, contest="1", index="A"
    )
    algo = Algorithm(title="Binary Search")
    graph = GraphBuilder([mistake, problem, algo]).build()
    result = KnowledgeCompiler(graph).compile(mistake)

    assert "Related Problems" in _headings(result.page)
    assert "Related Algorithms" in _headings(result.page)
