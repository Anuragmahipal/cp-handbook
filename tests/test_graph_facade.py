"""Tests for KnowledgeGraph: lookup, related/backlinks, and error handling."""

from __future__ import annotations

import pytest

from handbook.graph import GraphBuilder, NodeNotFoundError
from handbook.models import Algorithm, Problem, RelationType


def test_get_resolves_by_id_slug_alias_and_title():
    algo = Algorithm(title="Disjoint Set Union", aliases=["DSU"])
    graph = GraphBuilder([algo]).build()

    assert graph.get(algo.id) is not None
    assert graph.get(algo.slug) is not None
    assert graph.get("DSU") is not None
    assert graph.get("Disjoint Set Union") is not None
    assert (
        graph.get("disjoint set union") is not None
    )  # title lookup is case-insensitive


def test_get_returns_none_for_unknown_reference_without_creating_a_shadow():
    algo = Algorithm(title="Disjoint Set Union")
    graph = GraphBuilder([algo]).build()

    assert graph.get("Something That Does Not Exist") is None
    assert len(graph) == 1  # get() must never fabricate a node


def test_contains_and_len():
    algo = Algorithm(title="A")
    graph = GraphBuilder([algo]).build()

    assert len(graph) == 1
    assert algo.id in graph
    assert "nonexistent" not in graph


def test_related_returns_both_directions_by_default():
    algo = Algorithm(title="Algo")
    problem = Problem(
        title="Problem",
        platform="Codeforces",
        contest="R1",
        index="A",
        algorithms=["Algo"],
    )
    graph = GraphBuilder([algo, problem]).build()

    algo_related = graph.related(algo.id)
    problem_related = graph.related(problem.id)

    assert [n.id for _, n in algo_related] == [problem.id]
    assert [n.id for _, n in problem_related] == [algo.id]


def test_related_direction_filter():
    algo = Algorithm(title="Algo")
    problem = Problem(
        title="Problem",
        platform="Codeforces",
        contest="R1",
        index="A",
        algorithms=["Algo"],
    )
    graph = GraphBuilder([algo, problem]).build()

    assert graph.related(algo.id, direction="out") == []
    assert len(graph.related(algo.id, direction="in")) == 1


def test_related_relation_types_filter():
    algo = Algorithm(title="Algo")
    problem = Problem(
        title="Problem",
        platform="Codeforces",
        contest="R1",
        index="A",
        algorithms=["Algo"],
        related_items=[{"target": "Algo", "type": "related"}],
    )
    graph = GraphBuilder([algo, problem]).build()

    only_uses = graph.related(problem.id, relation_types=[RelationType.USES])
    assert len(only_uses) == 1
    assert only_uses[0][0].type == RelationType.USES


def test_backlinks_is_computed_from_edges_never_from_markdown():
    algo = Algorithm(title="Algo")
    p1 = Problem(
        title="P1", platform="Codeforces", contest="R1", index="A", algorithms=["Algo"]
    )
    p2 = Problem(
        title="P2", platform="Codeforces", contest="R1", index="B", algorithms=["Algo"]
    )
    graph = GraphBuilder([algo, p1, p2]).build()

    backlinks = graph.backlinks(algo.id)

    assert {n.id for _, n in backlinks} == {p1.id, p2.id}


def test_related_raises_for_unknown_reference():
    graph = GraphBuilder([Algorithm(title="Algo")]).build()

    with pytest.raises(NodeNotFoundError):
        graph.related("nonexistent")


def test_traversal_delegation_raises_for_unknown_reference():
    graph = GraphBuilder([Algorithm(title="Algo")]).build()

    with pytest.raises(NodeNotFoundError):
        graph.successors("nonexistent")

    with pytest.raises(NodeNotFoundError):
        graph.shortest_path("nonexistent", "also-nonexistent")


def test_search_engine_and_duplicate_detector_factories_are_wired_to_the_graph():
    a = Algorithm(title="Segment Tree")
    b = Algorithm(title="segment tree")
    graph = GraphBuilder([a, b]).build()

    assert graph.search_engine().search("segment tree")
    assert not graph.duplicate_detector().find_duplicates().is_empty()
