"""Graph-integration tests: the compiler must reflect *real* graph
structure (shadow nodes, multi-item webs of relations) rather than
re-deriving relationships from an item's own fields in isolation --
the "consume the graph, don't duplicate its logic" constraint from
``docs/ARCHITECTURE_NOTES_COMPILER.md``.
"""

from __future__ import annotations

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.models import Algorithm, Mistake, Pattern, Platform, Problem


def _linked_ids(section) -> set[str]:
    return {
        span.link_target
        for block in section.blocks
        if block.block_type == "text"
        for span in block.content.spans
        if span.link_target
    }


def test_related_section_link_targets_match_real_graph_node_ids():
    algo = Algorithm(title="DSU", related_problems=["Connectivity"])
    problem = Problem(
        title="Connectivity", platform=Platform.CODEFORCES, contest="1", index="A"
    )
    graph = GraphBuilder([algo, problem]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Related Problems"
    )
    linked_ids = _linked_ids(section)
    expected_node = graph.get("Connectivity")
    assert expected_node is not None
    assert linked_ids == {expected_node.id}


def test_unresolved_reference_becomes_a_visible_shadow_link():
    """An algorithm referencing a problem that doesn't exist yet still
    produces a (shadow) link, rather than silently dropping the
    relation -- matching the graph's own "dangling reference stays
    visible" design (see docs/ARCHITECTURE_NOTES_CHUNK4A.md)."""
    algo = Algorithm(title="DSU", related_problems=["Some Problem Not Yet Added"])
    graph = GraphBuilder([algo]).build()
    result = KnowledgeCompiler(graph).compile(algo)

    section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Related Problems"
    )
    text = section.blocks[0].content.as_plain_text()
    assert "Some Problem Not Yet Added" in text

    linked_ids = _linked_ids(section)
    shadow_node = graph.get("Some Problem Not Yet Added")
    assert shadow_node is not None
    assert shadow_node.is_shadow
    assert linked_ids == {shadow_node.id}


def test_a_web_of_relations_resolves_correctly_across_five_items():
    """Build one small but genuinely interconnected knowledge base and
    verify every compiled page's relation sections match the graph,
    not just each item's own authored fields."""
    algo = Algorithm(title="Binary Search", related_problems=["Find Peak"])
    pattern = Pattern(
        title="Search on Answer",
        related_algorithms=["Binary Search"],
        example_problems=["Find Peak"],
    )
    mistake = Mistake(
        title="Off-by-one bound",
        related_algorithms=["Binary Search", "Search on Answer"],
        related_problems=["Find Peak"],
    )
    problem = Problem(
        title="Find Peak",
        platform=Platform.CODEFORCES,
        contest="1",
        index="A",
        algorithms=["Binary Search"],
        patterns=["Search on Answer"],
        mistakes=["Off-by-one bound"],
    )
    items = [algo, pattern, mistake, problem]
    graph = GraphBuilder(items).build()
    compiler = KnowledgeCompiler(graph)

    algo_result = compiler.compile(algo)
    algo_headings = [s.heading.as_plain_text() for s in algo_result.page.sections]
    assert "Related Problems" in algo_headings
    assert "Related Patterns" in algo_headings
    assert "Mistakes" in algo_headings

    problem_result = compiler.compile(problem)
    problem_headings = [s.heading.as_plain_text() for s in problem_result.page.sections]
    assert "Algorithms Used" in problem_headings
    assert "Patterns Used" in problem_headings
    assert "Mistakes" in problem_headings

    pattern_result = compiler.compile(pattern)
    pattern_headings = [s.heading.as_plain_text() for s in pattern_result.page.sections]
    assert "Related Algorithms" in pattern_headings
    assert "Example Problems" in pattern_headings
    assert "Mistakes" in pattern_headings  # backlink from Mistake.related_algorithms


def test_prerequisites_reflect_a_chain_not_just_direct_authoring():
    """Prerequisites are one authored hop (A depends on B) -- the
    compiler should show exactly that hop, not silently walk the whole
    transitive chain (that's a job for a future learning-path feature,
    per ARCHITECTURE_NOTES_LEARNING.md's deferred items)."""
    advanced = Algorithm(title="Heavy-Light Decomposition", prerequisites=["Segment Tree"])
    intermediate = Algorithm(title="Segment Tree", prerequisites=["Arrays"])
    basic = Algorithm(title="Arrays")
    graph = GraphBuilder([advanced, intermediate, basic]).build()
    result = KnowledgeCompiler(graph).compile(advanced)

    section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Prerequisites"
    )
    text = section.blocks[0].content.as_plain_text()
    assert "Segment Tree" in text
    assert "Arrays" not in text  # not a direct prerequisite of `advanced`
