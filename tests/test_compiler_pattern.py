"""Tests for PatternCompiler, independent of every other compiler."""

from __future__ import annotations

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.learning.enums import CalloutKind
from handbook.models import Algorithm, Mistake, Pattern, Platform, Problem


def _headings(page) -> list[str]:
    return [s.heading.as_plain_text() for s in page.sections]


def test_minimal_pattern_produces_no_content_sections():
    pattern = Pattern(title="Bare Pattern")
    graph = GraphBuilder([pattern]).build()
    result = KnowledgeCompiler(graph).compile(pattern)

    assert _headings(result.page) == []
    assert any("no reviewable content" in w for w in result.warnings)


def test_description_and_recognition_cues_produce_their_sections():
    pattern = Pattern(
        title="Sliding Window",
        description="Maintain a moving range with two pointers.",
        recognition_cues=["contiguous subarray", "sum/count constraint"],
    )
    graph = GraphBuilder([pattern]).build()
    result = KnowledgeCompiler(graph).compile(pattern)

    assert _headings(result.page) == ["Intuition", "Recognition Cues"]
    cues_section = result.page.sections[1]
    callout = cues_section.blocks[0]
    assert callout.kind == CalloutKind.TIP
    assert [b.content.as_plain_text() for b in callout.body] == [
        "contiguous subarray",
        "sum/count constraint",
    ]


def test_memory_anchor_prefers_recognition_cues_over_intuition():
    pattern = Pattern(title="X", description="why", recognition_cues=["cue"])
    graph = GraphBuilder([pattern]).build()
    result = KnowledgeCompiler(graph).compile(pattern)

    cues_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Recognition Cues"
    )
    intuition_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Intuition"
    )
    assert len(cues_section.memory_anchors) == 1
    assert intuition_section.memory_anchors == ()


def test_related_algorithms_and_example_problems_from_graph():
    pattern = Pattern(
        title="Two Pointers",
        related_algorithms=["Sorting"],
        example_problems=["Pair Sum"],
    )
    sorting = Algorithm(title="Sorting")
    pair_sum = Problem(title="Pair Sum", platform=Platform.CODEFORCES, contest="1", index="A")
    graph = GraphBuilder([pattern, sorting, pair_sum]).build()
    result = KnowledgeCompiler(graph).compile(pattern)

    assert "Related Algorithms" in _headings(result.page)
    assert "Example Problems" in _headings(result.page)


def test_mistakes_backlink_resolves_by_title_regardless_of_source_kind():
    pattern = Pattern(title="Two Pointers")
    mistake = Mistake(title="Moved both pointers at once", related_algorithms=["Two Pointers"])
    graph = GraphBuilder([pattern, mistake]).build()
    result = KnowledgeCompiler(graph).compile(pattern)

    mistakes_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Mistakes"
    )
    assert "Moved both pointers at once" in mistakes_section.blocks[0].content.as_plain_text()
