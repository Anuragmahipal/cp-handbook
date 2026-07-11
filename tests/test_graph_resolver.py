"""Unit tests for Resolver: reference resolution order and shadow fallback."""

from __future__ import annotations

from handbook.graph.index import GraphIndex
from handbook.graph.node import Node
from handbook.graph.resolver import Resolver


def _node(node_id: str, title: str, **kwargs) -> Node:
    return Node(
        id=node_id,
        kind="algorithm",
        title=title,
        slug=title.lower().replace(" ", "-"),
        **kwargs,
    )


def test_resolve_by_id_takes_priority():
    index = GraphIndex()
    index.upsert_node(_node("1", "Segment Tree"))
    resolver = Resolver(index)

    assert resolver.resolve("1").id == "1"


def test_resolve_by_slug():
    index = GraphIndex()
    index.upsert_node(_node("1", "Segment Tree"))
    resolver = Resolver(index)

    assert resolver.resolve("segment-tree").id == "1"


def test_resolve_by_alias():
    index = GraphIndex()
    index.upsert_node(_node("1", "Disjoint Set Union", aliases=["DSU"]))
    resolver = Resolver(index)

    assert resolver.resolve("DSU").id == "1"


def test_resolve_by_title_case_insensitive():
    index = GraphIndex()
    index.upsert_node(_node("1", "Segment Tree"))
    resolver = Resolver(index)

    assert resolver.resolve("SEGMENT TREE").id == "1"


def test_resolve_falls_back_to_shadow_node():
    index = GraphIndex()
    resolver = Resolver(index)

    node = resolver.resolve("Nonexistent Thing")

    assert node.is_shadow is True
    assert index.node_count() == 1


def test_resolve_reuses_existing_shadow_node_across_calls():
    index = GraphIndex()
    resolver = Resolver(index)

    first = resolver.resolve("Ghost")
    second = resolver.resolve("ghost")

    assert first.id == second.id
    assert index.node_count() == 1


def test_resolve_id_convenience_method():
    index = GraphIndex()
    index.upsert_node(_node("1", "Segment Tree"))
    resolver = Resolver(index)

    assert resolver.resolve_id("Segment Tree") == "1"


def test_resolve_strips_whitespace():
    index = GraphIndex()
    index.upsert_node(_node("1", "Segment Tree"))
    resolver = Resolver(index)

    assert resolver.resolve("  Segment Tree  ").id == "1"
