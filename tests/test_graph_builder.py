"""Tests for GraphBuilder: turning KnowledgeItems into nodes and edges."""

from __future__ import annotations

from handbook.graph import EdgeDirection, GraphBuilder
from handbook.models import Algorithm, Contest, Pattern, Problem, RelationType, Topic


def test_build_creates_one_node_per_item():
    algo = Algorithm(title="Binary Lifting")
    problem = Problem(title="LCA", platform="Codeforces", contest="R1", index="A")

    graph = GraphBuilder([algo, problem]).build()

    assert len(graph) == 2
    assert graph.get(algo.id).title == "Binary Lifting"
    assert graph.get(problem.id).kind == "problem"


def test_node_projects_classification_metadata_not_body_text():
    algo = Algorithm(
        title="Binary Lifting",
        tags=["Tree", "LCA"],
        difficulty="Hard",
        aliases=["Jump Pointers"],
        notes="A very long explanation that should never end up on the node.",
    )

    graph = GraphBuilder([algo]).build()
    node = graph.get(algo.id)

    assert node.tags == ["tree", "lca"]  # normalized lowercase, per KnowledgeItem
    assert node.difficulty == "Hard"
    assert node.aliases == ["Jump Pointers"]
    assert not hasattr(node, "notes")


def test_edges_are_discovered_generically_across_relation_fields():
    """GraphBuilder must not hardcode field names: every list[Relation]
    field on every knowledge type should produce edges, including
    type-specific fields like Problem.algorithms, Contest.problems, and
    Topic.key_problems, as well as the shared base fields."""
    algo = Algorithm(title="Segment Tree")
    pattern = Pattern(title="Divide and Conquer", related_algorithms=["Segment Tree"])
    problem = Problem(
        title="Range Sum",
        platform="Codeforces",
        contest="R1",
        index="A",
        algorithms=["Segment Tree"],
        prerequisites=["Divide and Conquer"],
    )
    contest = Contest(title="R1", platform="Codeforces", problems=["Range Sum"])
    topic = Topic(
        title="Trees", key_problems=["Range Sum"], algorithms=["Segment Tree"]
    )

    graph = GraphBuilder([algo, pattern, problem, contest, topic]).build()

    edge_types = {e.type for e in graph.edges()}
    assert RelationType.USES in edge_types  # Problem.algorithms
    assert RelationType.PREREQUISITE in edge_types  # base prerequisites
    assert RelationType.CONTAINS in edge_types  # Contest.problems / Topic.algorithms
    assert (
        RelationType.APPEARS_IN in edge_types
    )  # Topic.key_problems / Pattern.related_*

    # Every edge should carry provenance naming the field it came from.
    assert all(e.provenance.startswith("field:") for e in graph.edges())


def test_relation_note_and_confidence_carry_through():
    algo = Algorithm(title="Binary Search")
    other = Algorithm(
        title="Ternary Search",
        prerequisites=[
            {"target": "Binary Search", "type": "related", "note": "same family"}
        ],
    )

    graph = GraphBuilder([algo, other]).build()
    edge = next(e for e in graph.edges() if e.source == other.id)

    assert edge.notes == "same family"
    assert edge.confidence == 1.0


def test_bidirectional_relation_types_get_bidirectional_edges():
    a = Algorithm(title="A", related_items=[{"target": "B", "type": "related"}])
    b = Algorithm(title="B")

    graph = GraphBuilder([a, b]).build()
    edge = next(e for e in graph.edges())

    assert edge.type == RelationType.RELATED
    assert edge.direction is EdgeDirection.BIDIRECTIONAL


def test_forward_relation_types_get_forward_edges():
    a = Algorithm(title="A")
    b = Algorithm(title="B", prerequisites=["A"])

    graph = GraphBuilder([a, b]).build()
    edge = next(e for e in graph.edges())

    assert edge.type == RelationType.PREREQUISITE
    assert edge.direction is EdgeDirection.FORWARD


# -- resolution order -----------------------------------------------------


def test_relation_resolves_to_real_node_by_title_regardless_of_order():
    """A relation authored before its target appears in the item list
    must still resolve to the real node, not a shadow -- resolution
    happens only after every node has been registered."""
    referencer = Algorithm(title="Referencer", related_items=["Referenced"])
    referenced = Algorithm(title="Referenced")

    graph = GraphBuilder([referencer, referenced]).build()
    edge = next(iter(graph.edges()))

    assert edge.target == referenced.id
    target_node = graph.get(referenced.id)
    assert target_node is not None and not target_node.is_shadow


def test_relation_resolves_by_slug():
    referenced = Algorithm(title="Binary Search Tree")
    referencer = Algorithm(title="Ref", related_items=["binary-search-tree"])

    graph = GraphBuilder([referencer, referenced]).build()
    edge = next(iter(graph.edges()))

    assert edge.target == referenced.id


def test_relation_resolves_by_alias():
    referenced = Algorithm(title="Disjoint Set Union", aliases=["DSU"])
    referencer = Algorithm(title="Ref", related_items=["DSU"])

    graph = GraphBuilder([referencer, referenced]).build()
    edge = next(iter(graph.edges()))

    assert edge.target == referenced.id


def test_relation_resolves_by_id():
    referenced = Algorithm(title="Fenwick Tree")
    referencer = Algorithm(title="Ref", related_items=[referenced.id])

    graph = GraphBuilder([referencer, referenced]).build()
    edge = next(iter(graph.edges()))

    assert edge.target == referenced.id


# -- shadow nodes -----------------------------------------------------------


def test_unresolved_target_becomes_a_shadow_node():
    referencer = Algorithm(title="Ref", related_items=["Nonexistent Thing"])

    graph = GraphBuilder([referencer]).build()
    edge = next(iter(graph.edges()))
    shadow = graph.get(edge.target)

    assert shadow is not None
    assert shadow.is_shadow is True
    assert shadow.title == "Nonexistent Thing"
    assert shadow.kind == "unknown"


def test_repeated_references_to_the_same_unresolved_target_converge():
    a = Algorithm(title="A", related_items=["Ghost"])
    b = Algorithm(title="B", related_items=["Ghost"])

    graph = GraphBuilder([a, b]).build()
    shadow_targets = {e.target for e in graph.edges()}

    assert len(shadow_targets) == 1
    assert len(graph) == 3  # A, B, and exactly one shadow node


# -- incremental rebuild ------------------------------------------------


def test_update_recomputes_only_edges_sourced_by_the_changed_item():
    algo = Algorithm(title="Algo")
    p1 = Problem(
        title="P1", platform="Codeforces", contest="R1", index="A", algorithms=["Algo"]
    )
    p2 = Problem(
        title="P2", platform="Codeforces", contest="R1", index="B", algorithms=["Algo"]
    )
    builder = GraphBuilder([algo, p1, p2])
    graph = builder.build()
    assert len(graph.edges()) == 2

    p1_updated = p1.model_copy(update={"algorithms": []})
    builder.update(graph, [p1_updated])

    assert len(graph.edges()) == 1
    remaining = next(iter(graph.edges()))
    assert remaining.source == p2.id
    assert graph.get(algo.id) is not None  # untouched node survives


def test_update_upserts_node_metadata():
    algo = Algorithm(title="Algo", tags=["old-tag"])
    builder = GraphBuilder([algo])
    graph = builder.build()

    updated = algo.model_copy(update={"tags": ["new-tag"]})
    builder.update(graph, [updated])

    assert graph.get(algo.id).tags == ["new-tag"]


def test_rebuild_is_an_alias_for_build():
    algo = Algorithm(title="Algo")
    builder = GraphBuilder([algo])

    assert len(builder.rebuild()) == len(builder.build())


def test_add_chains_and_builds_incrementally():
    a = Algorithm(title="A")
    b = Algorithm(title="B")

    graph = GraphBuilder().add(a).add(b).build()

    assert len(graph) == 2
