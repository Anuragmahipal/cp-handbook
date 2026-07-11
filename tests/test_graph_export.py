"""Tests for Exporter: JSON, Graphviz DOT, and NetworkX-compatible export."""

from __future__ import annotations

import json

from handbook.graph import GraphBuilder
from handbook.models import Algorithm, Problem


def _small_graph():
    algo = Algorithm(title="Binary Lifting")
    problem = Problem(
        title="LCA Queries",
        platform="Codeforces",
        contest="R1",
        index="A",
        algorithms=["Binary Lifting"],
    )
    return GraphBuilder([algo, problem]).build(), algo, problem


def test_export_json_round_trips_through_json_loads():
    graph, algo, problem = _small_graph()

    parsed = json.loads(graph.export_json())

    assert {n["id"] for n in parsed["nodes"]} == {algo.id, problem.id}
    assert len(parsed["edges"]) == 1
    assert parsed["edges"][0]["source"] == problem.id
    assert parsed["edges"][0]["target"] == algo.id


def test_export_json_indent_none_is_compact():
    graph, algo, problem = _small_graph()

    compact = graph.export_json(indent=None)
    pretty = graph.export_json()  # default indent=2

    assert "\n" not in compact
    assert "\n" in pretty
    assert json.loads(compact) == json.loads(pretty)


def test_export_dot_contains_every_node_and_edge():
    graph, algo, problem = _small_graph()

    dot = graph.export_dot()

    assert dot.startswith("digraph knowledge_graph {")
    assert dot.rstrip().endswith("}")
    assert f'"{algo.id}"' in dot
    assert f'"{problem.id}"' in dot
    assert f'"{problem.id}" -> "{algo.id}"' in dot
    assert 'label="uses"' in dot


def test_export_dot_marks_shadow_nodes_dashed():
    referencer = Algorithm(title="Ref", related_items=["Ghost"])
    graph = GraphBuilder([referencer]).build()

    dot = graph.export_dot()

    assert "style=dashed" in dot
    assert "style=solid" in dot


def test_export_dot_marks_bidirectional_edges():
    a = Algorithm(title="A", related_items=[{"target": "B", "type": "related"}])
    b = Algorithm(title="B")
    graph = GraphBuilder([a, b]).build()

    dot = graph.export_dot()

    assert "dir=both" in dot


def test_export_networkx_schema():
    graph, algo, problem = _small_graph()

    data = graph.export_networkx()

    assert data["directed"] is True
    assert data["multigraph"] is True
    assert data["graph"] == {}
    assert {n["id"] for n in data["nodes"]} == {algo.id, problem.id}
    assert len(data["links"]) == 1
    link = data["links"][0]
    assert link["source"] == problem.id
    assert link["target"] == algo.id
    assert "key" in link


def test_export_networkx_supports_multigraph_with_parallel_edges():
    a = Algorithm(title="A", related_items=["B", "B"])
    b = Algorithm(title="B")
    graph = GraphBuilder([a, b]).build()

    data = graph.export_networkx()

    assert len(data["links"]) == 2
    # Distinct keys, even though source/target/type are identical.
    assert data["links"][0]["key"] != data["links"][1]["key"]
