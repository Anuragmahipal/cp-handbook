"""Tests for Traversal: neighbors, reachability, paths, and DAG algorithms.

Uses ``RelationType.USES`` throughout for forward chains (rather than
``PREREQUISITE``) since edges follow literal authored direction -- see
the module docs on ``handbook.graph.edge`` for why a ``PREREQUISITE``
chain reads "dependent -> its prerequisite" and would make these tests
read backwards.
"""

from __future__ import annotations

import pytest

from handbook.graph import GraphBuilder, GraphCycleError
from handbook.models import Algorithm, Problem, RelationType


def _uses_chain(*titles: str) -> list[Problem]:
    """Build a straight-line chain problems[i] --USES--> problems[i+1]."""
    items = []
    for i, title in enumerate(titles):
        algorithms = [titles[i + 1]] if i + 1 < len(titles) else []
        items.append(
            Problem(
                title=title,
                platform="Codeforces",
                contest="R1",
                index=str(i),
                algorithms=algorithms,
            )
        )
    return items


def test_successors_and_predecessors_are_mirror_images():
    p1, p2 = _uses_chain("P1", "P2")
    graph = GraphBuilder([p1, p2]).build()

    assert graph.successors(p1.id) == [p2.id]
    assert graph.predecessors(p2.id) == [p1.id]
    assert graph.predecessors(p1.id) == []
    assert graph.successors(p2.id) == []


def test_neighbors_is_the_union_of_successors_and_predecessors():
    p1, p2, p3 = _uses_chain("P1", "P2", "P3")
    graph = GraphBuilder([p1, p2, p3]).build()

    assert set(graph.neighbors(p2.id)) == {p1.id, p3.id}


def test_relation_types_filter_restricts_traversal():
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

    only_uses = graph.successors(problem.id, relation_types=[RelationType.USES])
    only_related = graph.successors(problem.id, relation_types=[RelationType.RELATED])

    assert only_uses == [algo.id]
    assert only_related == [algo.id]
    assert graph.successors(problem.id, relation_types=[RelationType.CONTAINS]) == []


def test_bidirectional_edge_creates_symmetric_neighbors():
    a = Algorithm(title="A", related_items=[{"target": "B", "type": "related"}])
    b = Algorithm(title="B")
    graph = GraphBuilder([a, b]).build()

    assert graph.successors(a.id) == [b.id]
    assert graph.successors(b.id) == [a.id]  # symmetric, thanks to BIDIRECTIONAL
    assert graph.predecessors(a.id) == [b.id]
    assert graph.predecessors(b.id) == [a.id]


def test_reachable_follows_multiple_hops():
    p1, p2, p3, p4 = _uses_chain("P1", "P2", "P3", "P4")
    graph = GraphBuilder([p1, p2, p3, p4]).build()

    assert graph.reachable(p1.id) == {p2.id, p3.id, p4.id}


def test_reachable_respects_max_depth():
    p1, p2, p3, p4 = _uses_chain("P1", "P2", "P3", "P4")
    graph = GraphBuilder([p1, p2, p3, p4]).build()

    assert graph.reachable(p1.id, max_depth=1) == {p2.id}
    assert graph.reachable(p1.id, max_depth=2) == {p2.id, p3.id}


def test_closure_is_the_unbounded_reachable_set():
    p1, p2, p3 = _uses_chain("P1", "P2", "P3")
    graph = GraphBuilder([p1, p2, p3]).build()

    assert graph.closure(p1.id) == graph.reachable(p1.id, max_depth=None)


def test_shortest_path_found():
    p1, p2, p3 = _uses_chain("P1", "P2", "P3")
    graph = GraphBuilder([p1, p2, p3]).build()

    assert graph.shortest_path(p1.id, p3.id) == [p1.id, p2.id, p3.id]


def test_shortest_path_same_node():
    (p1,) = _uses_chain("P1")
    graph = GraphBuilder([p1]).build()

    assert graph.shortest_path(p1.id, p1.id) == [p1.id]


def test_shortest_path_unreachable_returns_none():
    p1, p2 = _uses_chain("P1", "P2")
    graph = GraphBuilder([p1, p2]).build()

    assert graph.shortest_path(p2.id, p1.id) is None


def test_subgraph_includes_only_selected_nodes_and_internal_edges():
    p1, p2, p3 = _uses_chain("P1", "P2", "P3")
    graph = GraphBuilder([p1, p2, p3]).build()

    sub = graph.subgraph([p1.id, p2.id])

    assert len(sub) == 2
    assert len(sub.edges()) == 1
    assert sub.get(p1.id) is not None
    assert sub.get(p3.id) is None


def test_subgraph_is_independent_of_the_parent_graph():
    p1, p2 = _uses_chain("P1", "P2")
    graph = GraphBuilder([p1, p2]).build()
    sub = graph.subgraph([p1.id, p2.id])

    # Mutating the subgraph's index must never touch the parent's.
    sub.index.remove_node(p2.id)

    assert graph.get(p2.id) is not None
    assert sub.get(p2.id) is None


def test_topological_sort_orders_by_literal_edge_direction():
    p1, p2, p3 = _uses_chain("P1", "P2", "P3")
    graph = GraphBuilder([p1, p2, p3]).build()

    order = graph.topological_sort()

    assert order.index(p1.id) < order.index(p2.id) < order.index(p3.id)


def test_topological_sort_raises_on_cycle():
    a = Problem(
        title="A", platform="Codeforces", contest="R1", index="A", algorithms=["B"]
    )
    b = Problem(
        title="B", platform="Codeforces", contest="R1", index="B", algorithms=["C"]
    )
    c = Problem(
        title="C", platform="Codeforces", contest="R1", index="C", algorithms=["A"]
    )
    graph = GraphBuilder([a, b, c]).build()

    with pytest.raises(GraphCycleError) as excinfo:
        graph.topological_sort()

    assert len(excinfo.value.cycle) >= 3


def test_cycle_detection_returns_empty_for_a_dag():
    p1, p2 = _uses_chain("P1", "P2")
    graph = GraphBuilder([p1, p2]).build()

    assert graph.cycle_detection() == []


def test_cycle_detection_finds_the_cycle():
    a = Problem(
        title="A", platform="Codeforces", contest="R1", index="A", algorithms=["B"]
    )
    b = Problem(
        title="B", platform="Codeforces", contest="R1", index="B", algorithms=["A"]
    )
    graph = GraphBuilder([a, b]).build()

    cycles = graph.cycle_detection()

    assert len(cycles) == 1
    assert cycles[0][0] == cycles[0][-1]


def test_bidirectional_edges_are_excluded_from_topological_sort_and_cycles():
    """A symmetric relation between two nodes is not a meaningful cycle."""
    a = Algorithm(title="A", related_items=[{"target": "B", "type": "related"}])
    b = Algorithm(title="B")
    graph = GraphBuilder([a, b]).build()

    assert graph.cycle_detection() == []
    order = graph.topological_sort()
    assert set(order) == {a.id, b.id}
