"""GraphIndex: the graph's core data store and every lookup built on it.

Every other class in this package -- :class:`~handbook.graph.resolver.
Resolver`, :class:`~handbook.graph.traversal.Traversal`,
:class:`~handbook.graph.search.SearchEngine`,
:class:`~handbook.graph.duplicates.DuplicateDetector`,
:class:`~handbook.graph.export.Exporter` -- reads from one ``GraphIndex``
instance rather than maintaining its own copy of the data. That's what
keeps the package's other classes small: they contribute *behavior*
(resolution, walking, ranking, formatting), while ``GraphIndex`` owns
the one copy of *state*.
"""

from __future__ import annotations

from collections.abc import Iterable

from handbook.graph.edge import Edge
from handbook.graph.node import Node


class GraphIndex:
    """Nodes, edges, and every secondary index over them, in memory."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []

        # secondary indices, all keyed by lowercase string -> node id(s)
        self._by_slug: dict[str, str] = {}
        self._by_alias: dict[str, list[str]] = {}
        self._by_title: dict[str, list[str]] = {}
        self._by_tag: dict[str, set[str]] = {}
        self._by_kind: dict[str, set[str]] = {}
        self._by_status: dict[str, set[str]] = {}

        # adjacency, keyed by node id
        self._out_edges: dict[str, list[Edge]] = {}
        self._in_edges: dict[str, list[Edge]] = {}

    # -- nodes ----------------------------------------------------------
    def upsert_node(self, node: Node) -> None:
        """Insert ``node``, or replace it in place if its id already exists.

        Replacing re-registers every secondary index entry, so a node
        whose title/aliases/tags changed since the last upsert doesn't
        leave stale index entries behind.
        """
        if node.id in self._nodes:
            self._deregister_node(node.id)
        self._nodes[node.id] = node
        self._out_edges.setdefault(node.id, [])
        self._in_edges.setdefault(node.id, [])

        self._by_slug[node.slug] = node.id
        self._by_title.setdefault(node.title.strip().lower(), []).append(node.id)
        for alias in node.aliases:
            self._by_alias.setdefault(alias.strip().lower(), []).append(node.id)
        for tag in node.tags:
            self._by_tag.setdefault(tag.lower(), set()).add(node.id)
        self._by_kind.setdefault(node.kind, set()).add(node.id)
        if node.status is not None:
            self._by_status.setdefault(node.status, set()).add(node.id)

    def _deregister_node(self, node_id: str) -> None:
        """Remove ``node_id`` from every secondary index (not adjacency)."""
        node = self._nodes.get(node_id)
        if node is None:
            return
        if self._by_slug.get(node.slug) == node_id:
            self._by_slug.pop(node.slug, None)
        title_key = node.title.strip().lower()
        self._pop_from_bucket(self._by_title, title_key, node_id)
        for alias in node.aliases:
            self._pop_from_bucket(self._by_alias, alias.strip().lower(), node_id)
        for tag in node.tags:
            bucket = self._by_tag.get(tag.lower())
            if bucket is not None:
                bucket.discard(node_id)
        bucket = self._by_kind.get(node.kind)
        if bucket is not None:
            bucket.discard(node_id)
        if node.status is not None:
            bucket = self._by_status.get(node.status)
            if bucket is not None:
                bucket.discard(node_id)

    @staticmethod
    def _pop_from_bucket(buckets: dict[str, list[str]], key: str, node_id: str) -> None:
        ids = buckets.get(key)
        if not ids:
            return
        if node_id in ids:
            ids.remove(node_id)
        if not ids:
            buckets.pop(key, None)

    def remove_node(self, node_id: str) -> None:
        """Remove ``node_id`` entirely: from every index, and every edge
        touching it. Used when a KnowledgeItem is deleted from the vault.
        """
        if node_id not in self._nodes:
            return
        self.remove_edges_touching(node_id)
        self._deregister_node(node_id)
        self._nodes.pop(node_id, None)
        self._out_edges.pop(node_id, None)
        self._in_edges.pop(node_id, None)

    def get_node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def find_by_slug(self, slug: str) -> Node | None:
        node_id = self._by_slug.get(slug)
        return self._nodes.get(node_id) if node_id is not None else None

    def find_by_alias(self, alias: str) -> list[Node]:
        ids = self._by_alias.get(alias.strip().lower(), [])
        return [self._nodes[i] for i in ids if i in self._nodes]

    def find_by_title(self, title: str) -> list[Node]:
        ids = self._by_title.get(title.strip().lower(), [])
        return [self._nodes[i] for i in ids if i in self._nodes]

    def by_tag(self, tag: str) -> list[Node]:
        return [self._nodes[i] for i in self._by_tag.get(tag.lower(), ())]

    def by_kind(self, kind: str) -> list[Node]:
        return [self._nodes[i] for i in self._by_kind.get(kind, ())]

    def by_status(self, status: str) -> list[Node]:
        return [self._nodes[i] for i in self._by_status.get(status, ())]

    def nodes(self) -> Iterable[Node]:
        return self._nodes.values()

    def node_ids(self) -> Iterable[str]:
        return self._nodes.keys()

    def node_count(self) -> int:
        return len(self._nodes)

    # -- shadow nodes -----------------------------------------------------
    def get_or_create_shadow(self, target: str) -> Node:
        """Return the shadow node for ``target``, creating it if needed.

        Deterministic id derivation (see :meth:`Node.shadow`) means every
        caller referencing the same unresolved name converges on one
        shared node instead of minting a duplicate per reference.
        """
        candidate = Node.shadow(target)
        existing = self._nodes.get(candidate.id)
        if existing is not None:
            return existing
        self.upsert_node(candidate)
        return candidate

    # -- edges --------------------------------------------------------------
    def add_edge(self, edge: Edge) -> None:
        self._edges.append(edge)
        self._out_edges.setdefault(edge.source, []).append(edge)
        self._in_edges.setdefault(edge.target, []).append(edge)

    def edges(self) -> Iterable[Edge]:
        return list(self._edges)

    def edge_count(self) -> int:
        return len(self._edges)

    def out_edges(self, node_id: str) -> list[Edge]:
        return list(self._out_edges.get(node_id, ()))

    def in_edges(self, node_id: str) -> list[Edge]:
        return list(self._in_edges.get(node_id, ()))

    def remove_edges_from(self, node_id: str) -> None:
        """Drop every edge *sourced by* ``node_id``.

        Used by :meth:`~handbook.graph.builder.GraphBuilder.update` to
        recompute one item's outgoing relations in isolation, without
        touching edges authored by any other item.
        """
        removed = self._out_edges.get(node_id)
        if not removed:
            return
        removed_ids = {id(e) for e in removed}
        self._out_edges[node_id] = []
        self._edges = [e for e in self._edges if id(e) not in removed_ids]
        for edge in removed:
            in_list = self._in_edges.get(edge.target)
            if in_list:
                self._in_edges[edge.target] = [
                    e for e in in_list if id(e) not in removed_ids
                ]

    def remove_edges_touching(self, node_id: str) -> None:
        """Drop every edge where ``node_id`` is the source or the target.

        Used by :meth:`remove_node` when a node is deleted outright.
        """
        touching = {id(e) for e in self._out_edges.get(node_id, ())}
        touching |= {id(e) for e in self._in_edges.get(node_id, ())}
        if not touching:
            return
        self._edges = [e for e in self._edges if id(e) not in touching]
        for src, lst in self._out_edges.items():
            if any(id(e) in touching for e in lst):
                self._out_edges[src] = [e for e in lst if id(e) not in touching]
        for tgt, lst in self._in_edges.items():
            if any(id(e) in touching for e in lst):
                self._in_edges[tgt] = [e for e in lst if id(e) not in touching]
        self._out_edges[node_id] = []
        self._in_edges[node_id] = []
