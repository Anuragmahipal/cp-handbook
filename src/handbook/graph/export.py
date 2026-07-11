"""Exporter: serializes a graph to interchange formats.

Deliberately independent of :class:`~handbook.graph.traversal.
Traversal`, :class:`~handbook.graph.search.SearchEngine`, and
:class:`~handbook.graph.duplicates.DuplicateDetector` -- it only ever
reads nodes/edges off the index and formats them, so adding a new
export format is never at risk of accidentally touching a graph
algorithm.
"""

from __future__ import annotations

import json

from handbook.graph.edge import Edge, EdgeDirection
from handbook.graph.index import GraphIndex
from handbook.graph.node import Node


class Exporter:
    """JSON, Graphviz DOT, and NetworkX-compatible export of a graph."""

    def __init__(self, index: GraphIndex) -> None:
        self._index = index

    def to_json_dict(self) -> dict:
        """Plain ``{"nodes": [...], "edges": [...]}`` structure."""
        return {
            "nodes": [self._node_dict(node) for node in self._index.nodes()],
            "edges": [self._edge_dict(edge) for edge in self._index.edges()],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_json_dict(), indent=indent, ensure_ascii=False)

    def to_dot(self, *, graph_name: str = "knowledge_graph") -> str:
        """Graphviz DOT source. Shadow nodes render dashed; bidirectional
        edges get ``dir=both``."""
        lines = [f"digraph {graph_name} {{"]
        for node in self._index.nodes():
            label = node.title.replace('"', '\\"')
            style = "dashed" if node.is_shadow else "solid"
            lines.append(f'  "{node.id}" [label="{label}", style={style}];')
        for edge in self._index.edges():
            attrs = f'label="{edge.type.value}"'
            if edge.direction is EdgeDirection.BIDIRECTIONAL:
                attrs += ", dir=both"
            lines.append(f'  "{edge.source}" -> "{edge.target}" [{attrs}];')
        lines.append("}")
        return "\n".join(lines)

    def to_networkx_dict(self) -> dict:
        """A NetworkX-compatible node-link structure.

        Matches the schema :func:`networkx.node_link_graph` expects
        (``nx.node_link_graph(exporter.to_networkx_dict())``) closely
        enough to round-trip, without this package depending on
        ``networkx`` itself. ``multigraph=True`` because multiple edges
        between the same pair of nodes are supported; each link gets a
        synthetic ``key`` since NetworkX requires one for multigraphs.
        """
        return {
            "directed": True,
            "multigraph": True,
            "graph": {},
            "nodes": [self._node_dict(node) for node in self._index.nodes()],
            "links": [
                {"key": f"{edge.type.value}:{i}", **self._edge_dict(edge)}
                for i, edge in enumerate(self._index.edges())
            ],
        }

    @staticmethod
    def _node_dict(node: Node) -> dict:
        return node.model_dump(mode="json")

    @staticmethod
    def _edge_dict(edge: Edge) -> dict:
        return edge.model_dump(mode="json")
