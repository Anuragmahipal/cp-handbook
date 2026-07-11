"""Unit tests for Node and Edge: the graph's data primitives."""

from __future__ import annotations

from handbook.graph.edge import Edge, EdgeDirection, default_direction
from handbook.graph.node import Node
from handbook.models import Algorithm, Difficulty, KnowledgeStatus, RelationType


def test_node_from_item_maps_enum_fields_to_their_string_values():
    algo = Algorithm(
        title="Binary Lifting",
        difficulty=Difficulty.HARD,
        status=KnowledgeStatus.LEARNING,
    )

    node = Node.from_item(algo)

    assert node.difficulty == "Hard"
    assert node.status == "Learning"
    assert node.is_shadow is False


def test_node_from_item_handles_missing_difficulty():
    algo = Algorithm(title="Binary Lifting")

    node = Node.from_item(algo)

    assert node.difficulty is None


def test_node_shadow_is_deterministic_for_the_same_target():
    first = Node.shadow("Segment Tree")
    second = Node.shadow("segment tree")  # different case, same slug

    assert first.id == second.id
    assert first.is_shadow is True


def test_node_shadow_differs_for_different_targets():
    a = Node.shadow("Segment Tree")
    b = Node.shadow("Fenwick Tree")

    assert a.id != b.id


def test_node_matches_text_checks_title_aliases_and_tags():
    node = Node(
        id="1",
        kind="algorithm",
        title="Disjoint Set Union",
        slug="disjoint-set-union",
        aliases=["DSU"],
        tags=["graph"],
    )

    assert node.matches_text("disjoint")
    assert node.matches_text("dsu")
    assert node.matches_text("graph")
    assert not node.matches_text("segment tree")


def test_default_direction_for_symmetric_relation_types():
    assert default_direction(RelationType.RELATED) is EdgeDirection.BIDIRECTIONAL
    assert default_direction(RelationType.SIMILAR_TO) is EdgeDirection.BIDIRECTIONAL
    assert default_direction(RelationType.CONTRASTS_WITH) is EdgeDirection.BIDIRECTIONAL


def test_default_direction_for_directed_relation_types():
    assert default_direction(RelationType.PREREQUISITE) is EdgeDirection.FORWARD
    assert default_direction(RelationType.USES) is EdgeDirection.FORWARD
    assert default_direction(RelationType.CONTAINS) is EdgeDirection.FORWARD


def test_edge_successor_of_forward_edge():
    edge = Edge(source="a", target="b", type=RelationType.USES)

    assert edge.successor_of("a") == "b"
    assert edge.successor_of("b") is None  # b is the target of a forward edge


def test_edge_predecessor_of_forward_edge():
    edge = Edge(source="a", target="b", type=RelationType.USES)

    assert edge.predecessor_of("b") == "a"
    assert edge.predecessor_of("a") is None


def test_edge_successor_and_predecessor_of_bidirectional_edge():
    edge = Edge(
        source="a",
        target="b",
        type=RelationType.RELATED,
        direction=EdgeDirection.BIDIRECTIONAL,
    )

    assert edge.successor_of("a") == "b"
    assert edge.successor_of("b") == "a"
    assert edge.predecessor_of("a") == "b"
    assert edge.predecessor_of("b") == "a"


def test_edge_successor_of_returns_none_for_unrelated_node():
    edge = Edge(source="a", target="b", type=RelationType.USES)

    assert edge.successor_of("c") is None
    assert edge.predecessor_of("c") is None


def test_edge_endpoints():
    edge = Edge(source="a", target="b", type=RelationType.USES)

    assert edge.endpoints() == ("a", "b")


def test_edge_confidence_defaults_and_bounds():
    edge = Edge(source="a", target="b", type=RelationType.USES)

    assert edge.confidence == 1.0
