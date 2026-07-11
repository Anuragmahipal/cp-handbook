"""Unit tests for GraphIndex: node/edge storage and every lookup over it."""

from __future__ import annotations

from handbook.graph.edge import Edge
from handbook.graph.index import GraphIndex
from handbook.graph.node import Node
from handbook.models import RelationType


def _node(node_id: str, title: str, **kwargs) -> Node:
    return Node(
        id=node_id,
        kind=kwargs.pop("kind", "algorithm"),
        title=title,
        slug=title.lower().replace(" ", "-"),
        **kwargs,
    )


def test_upsert_and_get_node():
    index = GraphIndex()
    node = _node("1", "Segment Tree")

    index.upsert_node(node)

    assert index.get_node("1") is node
    assert index.node_count() == 1


def test_upsert_replaces_existing_node_and_stale_index_entries():
    index = GraphIndex()
    index.upsert_node(_node("1", "Old Title", aliases=["Old Alias"]))

    index.upsert_node(_node("1", "New Title", aliases=["New Alias"]))

    assert index.get_node("1").title == "New Title"
    assert index.find_by_title("Old Title") == []
    assert index.find_by_alias("Old Alias") == []
    assert index.find_by_title("New Title")[0].id == "1"
    assert index.find_by_alias("New Alias")[0].id == "1"
    assert index.node_count() == 1


def test_find_by_slug_alias_title():
    index = GraphIndex()
    index.upsert_node(_node("1", "Disjoint Set Union", aliases=["DSU"]))

    assert index.find_by_slug("disjoint-set-union").id == "1"
    assert index.find_by_alias("dsu")[0].id == "1"  # case-insensitive
    assert index.find_by_title("disjoint set union")[0].id == "1"


def test_find_by_alias_and_title_return_multiple_on_collision():
    index = GraphIndex()
    index.upsert_node(_node("1", "Segment Tree"))
    index.upsert_node(_node("2", "segment tree"))

    matches = index.find_by_title("Segment Tree")

    assert {n.id for n in matches} == {"1", "2"}


def test_by_tag_kind_status():
    index = GraphIndex()
    index.upsert_node(_node("1", "A", tags=["tree"], kind="algorithm", status="Active"))
    index.upsert_node(
        _node("2", "B", tags=["graph"], kind="problem", status="Mastered")
    )

    assert [n.id for n in index.by_tag("tree")] == ["1"]
    assert [n.id for n in index.by_kind("problem")] == ["2"]
    assert [n.id for n in index.by_status("Mastered")] == ["2"]


def test_get_or_create_shadow_deduplicates():
    index = GraphIndex()

    first = index.get_or_create_shadow("Ghost")
    second = index.get_or_create_shadow("ghost")

    assert first.id == second.id
    assert index.node_count() == 1


def test_add_edge_registers_adjacency_both_ways():
    index = GraphIndex()
    edge = Edge(source="a", target="b", type=RelationType.USES)

    index.add_edge(edge)

    assert index.out_edges("a") == [edge]
    assert index.in_edges("b") == [edge]
    assert index.out_edges("b") == []
    assert list(index.edges()) == [edge]


def test_remove_edges_from_only_drops_edges_sourced_by_that_node():
    index = GraphIndex()
    e1 = Edge(source="a", target="b", type=RelationType.USES)
    e2 = Edge(source="c", target="b", type=RelationType.USES)
    index.add_edge(e1)
    index.add_edge(e2)

    index.remove_edges_from("a")

    assert index.out_edges("a") == []
    assert index.in_edges("b") == [e2]
    assert list(index.edges()) == [e2]


def test_remove_node_cascades_to_touching_edges():
    index = GraphIndex()
    index.upsert_node(_node("a", "A"))
    index.upsert_node(_node("b", "B"))
    edge = Edge(source="a", target="b", type=RelationType.USES)
    index.add_edge(edge)

    index.remove_node("b")

    assert index.get_node("b") is None
    assert index.out_edges("a") == []
    assert list(index.edges()) == []


def test_remove_node_cleans_up_secondary_indices():
    index = GraphIndex()
    index.upsert_node(_node("1", "Segment Tree", aliases=["Seg Tree"], tags=["tree"]))

    index.remove_node("1")

    assert index.find_by_slug("segment-tree") is None
    assert index.find_by_alias("Seg Tree") == []
    assert index.find_by_title("Segment Tree") == []
    assert index.by_tag("tree") == []
    assert index.node_count() == 0
