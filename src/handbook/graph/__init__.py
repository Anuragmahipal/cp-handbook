"""The knowledge graph layer: the canonical runtime representation of
relationships between KnowledgeItems.

The vault (Markdown files on disk) remains the source of truth; this
package builds a derived, in-memory index on top of it::

    from handbook.graph import GraphBuilder

    graph = GraphBuilder(items).build()
    graph.get("Binary Lifting")
    graph.related("Two Sum")
    graph.backlinks("Segment Tree")
    graph.export_json()
    graph.export_dot()

    search = graph.search_engine()
    search.search("segment tree")

    duplicates = graph.duplicate_detector()
    duplicates.find_duplicates()

Every class here does one thing:

* :class:`~handbook.graph.node.Node` / :class:`~handbook.graph.edge.Edge`
  -- the graph's vertex/edge data, projected from ``KnowledgeItem`` /
  ``Relation``.
* :class:`~handbook.graph.index.GraphIndex` -- the single in-memory store
  of nodes/edges and every lookup index over them.
* :class:`~handbook.graph.resolver.Resolver` -- turns a raw reference
  string into a node, permissively (falls back to a shadow node).
* :class:`~handbook.graph.builder.GraphBuilder` -- derives a graph from
  ``KnowledgeItem`` instances; supports incremental updates.
* :class:`~handbook.graph.traversal.Traversal` -- neighbor/reachability/
  path/DAG algorithms, read-only over a ``GraphIndex``.
* :class:`~handbook.graph.search.SearchEngine` -- ranked search plus
  prefix and relation queries.
* :class:`~handbook.graph.duplicates.DuplicateDetector` -- modular,
  pluggable duplicate detection.
* :class:`~handbook.graph.export.Exporter` -- JSON / DOT / NetworkX-
  compatible serialization.
* :class:`~handbook.graph.graph.KnowledgeGraph` -- the facade composing
  all of the above into one convenient object.
"""

from __future__ import annotations

from handbook.graph.builder import GraphBuilder
from handbook.graph.duplicates import (
    DuplicateDetector,
    DuplicateEdgeGroup,
    DuplicateGroup,
    DuplicateReport,
    ExtraDetector,
)
from handbook.graph.edge import Edge, EdgeDirection, default_direction
from handbook.graph.exceptions import GraphCycleError, GraphError, NodeNotFoundError
from handbook.graph.export import Exporter
from handbook.graph.graph import KnowledgeGraph
from handbook.graph.index import GraphIndex
from handbook.graph.node import Node
from handbook.graph.resolver import Resolver
from handbook.graph.search import SearchEngine, SearchResult
from handbook.graph.traversal import Traversal

__all__ = [
    # facade
    "KnowledgeGraph",
    "GraphBuilder",
    # data
    "Node",
    "Edge",
    "EdgeDirection",
    "default_direction",
    # store + collaborators
    "GraphIndex",
    "Resolver",
    "Traversal",
    "SearchEngine",
    "SearchResult",
    "DuplicateDetector",
    "DuplicateGroup",
    "DuplicateEdgeGroup",
    "DuplicateReport",
    "ExtraDetector",
    "Exporter",
    # exceptions
    "GraphError",
    "NodeNotFoundError",
    "GraphCycleError",
]
