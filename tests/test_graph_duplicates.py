"""Tests for DuplicateDetector: exact and near-duplicate detection."""

from __future__ import annotations

from handbook.graph import DuplicateGroup, GraphBuilder
from handbook.models import Algorithm


def test_duplicate_titles_detected_case_and_whitespace_insensitively():
    a = Algorithm(title="Segment Tree")
    b = Algorithm(title="segment tree")
    graph = GraphBuilder([a, b]).build()

    groups = graph.duplicate_detector().find_duplicate_titles()

    assert len(groups) == 1
    assert set(groups[0].node_ids) == {a.id, b.id}


def test_distinct_titles_are_not_flagged():
    a = Algorithm(title="Segment Tree")
    b = Algorithm(title="Fenwick Tree")
    graph = GraphBuilder([a, b]).build()

    assert graph.duplicate_detector().find_duplicate_titles() == []


def test_duplicate_alias_across_two_nodes():
    a = Algorithm(title="Disjoint Set Union", aliases=["DSU"])
    b = Algorithm(title="Diagonal Sum Update", aliases=["DSU"])
    graph = GraphBuilder([a, b]).build()

    groups = graph.duplicate_detector().find_duplicate_aliases()

    assert len(groups) == 1
    assert set(groups[0].node_ids) == {a.id, b.id}


def test_alias_colliding_with_another_nodes_title_is_flagged():
    a = Algorithm(title="Union Find")
    b = Algorithm(title="Something Else", aliases=["Union Find"])
    graph = GraphBuilder([a, b]).build()

    groups = graph.duplicate_detector().find_duplicate_aliases()

    assert any({a.id, b.id} == set(g.node_ids) for g in groups)


def test_near_duplicate_names_detected_above_threshold():
    a = Algorithm(title="Binary Exponentiation")
    b = Algorithm(title="Binary Exponentation")  # one letter dropped
    graph = GraphBuilder([a, b]).build()

    groups = graph.duplicate_detector().find_near_duplicate_names()

    assert len(groups) == 1
    assert set(groups[0].node_ids) == {a.id, b.id}


def test_near_duplicate_names_excludes_exact_duplicates():
    """Exact duplicates are find_duplicate_titles()'s job, not this one's."""
    a = Algorithm(title="Segment Tree")
    b = Algorithm(title="Segment Tree")
    graph = GraphBuilder([a, b]).build()

    assert graph.duplicate_detector().find_near_duplicate_names() == []


def test_near_duplicate_threshold_is_configurable():
    a = Algorithm(title="Binary Search")
    b = Algorithm(title="Ternary Search")  # loosely similar, not a near-dup by default
    graph = GraphBuilder([a, b]).build()

    default_detector = graph.duplicate_detector()
    assert default_detector.find_near_duplicate_names() == []

    lenient_detector = graph.duplicate_detector(near_duplicate_threshold=0.3)
    assert lenient_detector.find_near_duplicate_names() != []


def test_duplicate_edges_detected():
    a = Algorithm(title="A", related_items=["B", "B"])
    b = Algorithm(title="B")
    graph = GraphBuilder([a, b]).build()

    groups = graph.duplicate_detector().find_duplicate_edges()

    assert len(groups) == 1
    assert groups[0].count == 2
    assert groups[0].source == a.id
    assert groups[0].target == b.id


def test_single_edge_between_a_pair_is_not_flagged():
    a = Algorithm(title="A", related_items=["B"])
    b = Algorithm(title="B")
    graph = GraphBuilder([a, b]).build()

    assert graph.duplicate_detector().find_duplicate_edges() == []


def test_find_duplicates_aggregates_every_category():
    a = Algorithm(title="Segment Tree")
    b = Algorithm(title="segment tree")
    graph = GraphBuilder([a, b]).build()

    report = graph.duplicate_detector().find_duplicates()

    assert not report.is_empty()
    assert len(report.duplicate_titles) == 1
    assert report.duplicate_edges == []
    assert report.extra == []


def test_empty_report_when_nothing_is_duplicated():
    a = Algorithm(title="Segment Tree")
    b = Algorithm(title="Fenwick Tree")
    graph = GraphBuilder([a, b]).build()

    assert graph.duplicate_detector().find_duplicates().is_empty()


def test_extra_detectors_are_pluggable():
    """The seam a future semantic/embeddings-based detector plugs into."""
    a = Algorithm(title="Segment Tree")
    graph = GraphBuilder([a]).build()

    def always_flag_everything(index):
        return [
            DuplicateGroup(reason="semantic", node_ids=[n.id for n in index.nodes()])
        ]

    detector = graph.duplicate_detector(extra_detectors=[always_flag_everything])
    report = detector.find_duplicates()

    assert len(report.extra) == 1
    assert report.extra[0].reason == "semantic"
    assert not report.is_empty()
