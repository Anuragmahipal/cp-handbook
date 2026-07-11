"""GraphBuilder: derives a KnowledgeGraph from KnowledgeItem instances.

The graph is a *derived index* -- the vault (files on disk) remains the
source of truth. ``GraphBuilder`` never touches the filesystem itself;
it takes already-parsed :class:`~handbook.models.base.KnowledgeItem`
objects from whoever has them (a future vault loader, a test fixture, an
in-memory list) and turns them into nodes and edges. That separation is
what lets this class -- and everything built on it -- be exercised in
tests with zero I/O, and lets a future incremental vault-watcher reuse
:meth:`update` without this package ever needing to know what a
filesystem is.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from handbook.graph.edge import Edge, default_direction
from handbook.graph.graph import KnowledgeGraph
from handbook.graph.index import GraphIndex
from handbook.graph.node import Node
from handbook.graph.resolver import Resolver
from handbook.models.base import KnowledgeItem, Relation


class GraphBuilder:
    """Builds (or incrementally updates) a :class:`KnowledgeGraph`.

    Usage::

        graph = GraphBuilder(items).build()

    or, built up incrementally::

        graph = GraphBuilder().add(item_a).add(item_b).build()
    """

    def __init__(self, items: Iterable[KnowledgeItem] | None = None) -> None:
        self._items: list[KnowledgeItem] = list(items) if items is not None else []

    def add(self, item: KnowledgeItem) -> GraphBuilder:
        """Queue one more item for the next :meth:`build`. Returns ``self``
        for chaining."""
        self._items.append(item)
        return self

    def build(self) -> KnowledgeGraph:
        """Build a fresh :class:`KnowledgeGraph` from every queued item.

        Two passes, deliberately in this order:

        1. Register a real :class:`~handbook.graph.node.Node` for every
           item, *before* any relation is resolved. This is what lets a
           relation authored on item A, pointing at item B, resolve to
           B's real node regardless of which of A/B appears first in
           ``items`` -- resolution never depends on iteration order.
        2. Walk every item's relation fields and resolve each target,
           creating shadow nodes for anything that still doesn't match.
        """
        index = GraphIndex()
        for item in self._items:
            index.upsert_node(Node.from_item(item))

        resolver = Resolver(index)
        for item in self._items:
            self._add_edges_for(item, index, resolver)

        return KnowledgeGraph(index)

    def rebuild(self) -> KnowledgeGraph:
        """Alias for :meth:`build`.

        Named separately so call sites that are explicitly re-deriving
        the graph after a vault change (as opposed to building it for
        the first time) read that way.
        """
        return self.build()

    def update(
        self, graph: KnowledgeGraph, items: Iterable[KnowledgeItem]
    ) -> KnowledgeGraph:
        """Incrementally re-derive nodes/edges for ``items`` in place.

        For each item: its node is upserted, and every edge it *sources*
        is dropped and recomputed from its current relation fields.
        Edges authored by other, unchanged items are left completely
        untouched -- this is what makes an update proportional to the
        number of changed items rather than to the size of the whole
        vault, satisfying "support future incremental rebuilding"
        without requiring a full :meth:`build` after every small edit.

        Returns ``graph`` (mutated), for convenient chaining.
        """
        items = list(items)
        index = graph.index

        for item in items:
            index.upsert_node(Node.from_item(item))

        resolver = Resolver(index)
        for item in items:
            index.remove_edges_from(item.id)
            self._add_edges_for(item, index, resolver)

        return graph

    @staticmethod
    def _relation_fields(item: KnowledgeItem) -> Iterator[tuple[str, Relation]]:
        """Yield ``(field_name, relation)`` for every Relation this item carries.

        Fields are discovered generically off the item's own Pydantic
        schema rather than a hardcoded per-knowledge-type field list
        (``Problem.algorithms``, ``Contest.problems``, ``Topic.
        key_problems``, ...). That genericism is the whole point: a new
        knowledge type can add a new ``list[Relation]`` field without
        ever requiring a change here.
        """
        for field_name in type(item).model_fields:
            value = getattr(item, field_name)
            if isinstance(value, Relation):
                yield field_name, value
            elif (
                isinstance(value, list)
                and value
                and all(isinstance(v, Relation) for v in value)
            ):
                for relation in value:
                    yield field_name, relation

    def _add_edges_for(
        self, item: KnowledgeItem, index: GraphIndex, resolver: Resolver
    ) -> None:
        for field_name, relation in self._relation_fields(item):
            target_node = resolver.resolve(relation.target)
            index.add_edge(
                Edge(
                    source=item.id,
                    target=target_node.id,
                    type=relation.type,
                    direction=default_direction(relation.type),
                    provenance=f"field:{field_name}",
                    notes=relation.note,
                )
            )
