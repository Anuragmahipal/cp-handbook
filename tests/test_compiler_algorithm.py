"""Tests for AlgorithmCompiler, independent of every other compiler."""

from __future__ import annotations

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.learning.enums import CalloutKind, ReviewStatus
from handbook.models import Algorithm, Mistake, Pattern, Platform, Problem


def _headings(page) -> list[str]:
    return [s.heading.as_plain_text() for s in page.sections]


def test_minimal_algorithm_produces_no_content_sections():
    algo = Algorithm(title="Bare Algorithm")
    graph = GraphBuilder([algo]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    assert _headings(result.page) == []
    assert result.page.metadata.title == "Bare Algorithm"
    assert any("no reviewable content" in w for w in result.warnings)


def test_fully_populated_algorithm_gets_every_section():
    algo = Algorithm(
        title="Segment Tree",
        intuition="Split the array into a binary tree of ranges.",
        implementation="build(1, 0, n - 1);",
        time_complexity="O(log n) per query",
        space_complexity="O(n)",
        pitfalls=["Forgetting to propagate lazy updates", "1-indexing bugs"],
    )
    graph = GraphBuilder([algo]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    assert _headings(result.page) == [
        "Intuition",
        "Complexity",
        "Implementation",
        "Pitfalls",
    ]


def test_implementation_uses_cpp_as_default_language():
    algo = Algorithm(title="X", implementation="int main() {}")
    graph = GraphBuilder([algo]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    code_section = next(s for s in result.page.sections if s.heading.as_plain_text() == "Implementation")
    assert code_section.blocks[0].language == "cpp"
    assert code_section.blocks[0].source == "int main() {}"


def test_pitfalls_become_a_bulleted_pitfall_callout():
    algo = Algorithm(title="X", pitfalls=["Off-by-one", "Integer overflow"])
    graph = GraphBuilder([algo]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    section = next(s for s in result.page.sections if s.heading.as_plain_text() == "Pitfalls")
    callout = section.blocks[0]
    assert callout.kind == CalloutKind.PITFALL
    assert [b.content.as_plain_text() for b in callout.body] == [
        "Off-by-one",
        "Integer overflow",
    ]


def test_memory_anchor_prefers_implementation_over_intuition():
    algo = Algorithm(title="X", intuition="why", implementation="how")
    graph = GraphBuilder([algo]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    impl_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Implementation"
    )
    intuition_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Intuition"
    )
    assert len(impl_section.memory_anchors) == 1
    assert impl_section.memory_anchors[0].target_id == impl_section.blocks[0].id
    assert intuition_section.memory_anchors == ()
    assert impl_section.review_cues[0].status == ReviewStatus.NEW
    assert impl_section.review_cues[0].strength == 0.0


def test_memory_anchor_falls_back_to_intuition_without_implementation():
    algo = Algorithm(title="X", intuition="why only")
    graph = GraphBuilder([algo]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    intuition_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Intuition"
    )
    assert len(intuition_section.memory_anchors) == 1


def test_related_problems_merges_authored_and_backlinked_relations():
    algo = Algorithm(title="Binary Lifting", related_problems=["Authored Problem"])
    authored = Problem(
        title="Authored Problem", platform=Platform.CODEFORCES, contest="1", index="A"
    )
    backlinked = Problem(
        title="Backlinked Problem",
        platform=Platform.CODEFORCES,
        contest="1",
        index="B",
        algorithms=["Binary Lifting"],
    )
    graph = GraphBuilder([algo, authored, backlinked]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Related Problems"
    )
    text = section.blocks[0].content.as_plain_text()
    assert "Authored Problem" in text
    assert "Backlinked Problem" in text


def test_related_problems_deduplicates_when_both_sides_author_the_link():
    algo = Algorithm(title="Binary Lifting", related_problems=["Shared Problem"])
    shared = Problem(
        title="Shared Problem",
        platform=Platform.CODEFORCES,
        contest="1",
        index="A",
        algorithms=["Binary Lifting"],
    )
    graph = GraphBuilder([algo, shared]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Related Problems"
    )
    assert section.blocks[0].content.as_plain_text().count("Shared Problem") == 1


def test_related_patterns_reads_pattern_backlinks_only():
    algo = Algorithm(title="Binary Search")
    pattern = Pattern(title="Search on Answer", related_algorithms=["Binary Search"])
    mistake = Mistake(title="Off by one", related_algorithms=["Binary Search"])
    graph = GraphBuilder([algo, pattern, mistake]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    patterns_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Related Patterns"
    )
    mistakes_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Mistakes"
    )
    assert "Search on Answer" in patterns_section.blocks[0].content.as_plain_text()
    assert "Off by one" not in patterns_section.blocks[0].content.as_plain_text()
    assert "Off by one" in mistakes_section.blocks[0].content.as_plain_text()
    assert "Search on Answer" not in mistakes_section.blocks[0].content.as_plain_text()


def test_prerequisites_section_reflects_graph_edges():
    algo = Algorithm(title="Heavy-Light Decomposition", prerequisites=["Segment Tree", "DFS"])
    segment_tree = Algorithm(title="Segment Tree")
    dfs = Algorithm(title="DFS")
    graph = GraphBuilder([algo, segment_tree, dfs]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Prerequisites"
    )
    text = section.blocks[0].content.as_plain_text()
    assert "Segment Tree" in text
    assert "DFS" in text


def test_item_not_in_graph_omits_relation_sections_without_raising():
    algo = Algorithm(title="Not In Graph", intuition="still compiles")
    empty_graph = GraphBuilder([]).build()  # algo was never added
    result = KnowledgeCompiler(empty_graph).compile(algo)

    assert _headings(result.page) == ["Intuition"]
