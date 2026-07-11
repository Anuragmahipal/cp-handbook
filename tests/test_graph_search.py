"""Tests for SearchEngine: ranked search, prefix search, relation queries."""

from __future__ import annotations

from handbook.graph import GraphBuilder
from handbook.models import Algorithm, Problem, RelationType


def test_exact_title_match_ranks_highest():
    exact = Algorithm(title="Segment Tree")
    partial = Algorithm(title="Segment Tree Beats")
    graph = GraphBuilder([exact, partial]).build()

    results = graph.search_engine().search("Segment Tree")

    assert results[0].node.id == exact.id
    assert results[0].matched_field == "title"


def test_alias_match_is_found():
    algo = Algorithm(title="Disjoint Set Union", aliases=["DSU"])
    graph = GraphBuilder([algo]).build()

    results = graph.search_engine().search("DSU")

    assert results
    assert results[0].node.id == algo.id
    assert results[0].matched_field == "aliases"


def test_prefix_match_outranks_substring_match():
    prefix_match = Algorithm(title="Binary Search")
    substring_match = Algorithm(title="Exponential Binary Search Variant")
    graph = GraphBuilder([prefix_match, substring_match]).build()

    results = graph.search_engine().search("Binary")

    assert results[0].node.id == prefix_match.id


def test_fuzzy_match_finds_a_slight_misspelling():
    algo = Algorithm(title="Fenwick Tree")
    graph = GraphBuilder([algo]).build()

    results = graph.search_engine().search("Fenwik Tree")

    assert any(r.node.id == algo.id for r in results)


def test_no_match_returns_empty_list():
    algo = Algorithm(title="Fenwick Tree")
    graph = GraphBuilder([algo]).build()

    assert graph.search_engine().search("Completely Unrelated Query") == []


def test_blank_query_returns_empty_list():
    algo = Algorithm(title="Fenwick Tree")
    graph = GraphBuilder([algo]).build()

    assert graph.search_engine().search("   ") == []


def test_kind_filter_excludes_other_knowledge_types():
    algo = Algorithm(title="Binary Search")
    problem = Problem(
        title="Binary Search Problem",
        platform="Codeforces",
        contest="R1",
        index="A",
    )
    graph = GraphBuilder([algo, problem]).build()

    results = graph.search_engine().search("Binary Search", kind="algorithm")

    assert {r.node.id for r in results} == {algo.id}


def test_tags_filter():
    tagged = Algorithm(title="Segment Tree", tags=["tree"])
    untagged = Algorithm(title="Segment Tree Lazy", tags=["lazy-propagation"])
    graph = GraphBuilder([tagged, untagged]).build()

    results = graph.search_engine().search("Segment Tree", tags=["tree"])

    assert {r.node.id for r in results} == {tagged.id}


def test_shadow_nodes_excluded_by_default_but_included_on_request():
    referencer = Algorithm(title="Ref", related_items=["Ghost Algorithm"])
    graph = GraphBuilder([referencer]).build()

    assert graph.search_engine().search("Ghost Algorithm") == []
    included = graph.search_engine().search("Ghost Algorithm", include_shadow=True)
    assert any(r.node.title == "Ghost Algorithm" for r in included)


def test_prefix_search():
    match = Algorithm(title="Binary Lifting")
    no_match = Algorithm(title="Segment Tree")
    graph = GraphBuilder([match, no_match]).build()

    results = graph.search_engine().prefix("Binary")

    assert [n.id for n in results] == [match.id]


def test_prefix_search_blank_returns_empty():
    algo = Algorithm(title="Binary Lifting")
    graph = GraphBuilder([algo]).build()

    assert graph.search_engine().prefix("") == []


def test_by_relation_out_direction_finds_sources_pointing_at_target():
    algo = Algorithm(title="Binary Lifting")
    p1 = Problem(
        title="P1",
        platform="Codeforces",
        contest="R1",
        index="A",
        algorithms=["Binary Lifting"],
    )
    p2 = Problem(
        title="P2",
        platform="Codeforces",
        contest="R1",
        index="B",
        algorithms=["Binary Lifting"],
    )
    unrelated = Problem(title="P3", platform="Codeforces", contest="R1", index="C")
    graph = GraphBuilder([algo, p1, p2, unrelated]).build()

    results = graph.search_engine().by_relation(
        RelationType.USES, target="Binary Lifting"
    )

    assert {n.id for n in results} == {p1.id, p2.id}


def test_by_relation_in_direction_finds_targets_of_source():
    algo1 = Algorithm(title="Binary Lifting")
    algo2 = Algorithm(title="Sparse Table")
    problem = Problem(
        title="P1",
        platform="Codeforces",
        contest="R1",
        index="A",
        algorithms=["Binary Lifting", "Sparse Table"],
    )
    graph = GraphBuilder([algo1, algo2, problem]).build()

    results = graph.search_engine().by_relation(
        RelationType.USES, target=problem.id, direction="in"
    )

    assert {n.id for n in results} == {algo1.id, algo2.id}


def test_by_relation_without_target_returns_every_node_of_that_type():
    algo = Algorithm(title="Binary Lifting")
    p1 = Problem(
        title="P1",
        platform="Codeforces",
        contest="R1",
        index="A",
        algorithms=["Binary Lifting"],
    )
    graph = GraphBuilder([algo, p1]).build()

    results = graph.search_engine().by_relation(RelationType.USES)

    assert {n.id for n in results} == {p1.id}
