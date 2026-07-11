"""KnowledgeGraph: the canonical runtime representation of relationships.

A thin facade over :class:`~handbook.graph.index.GraphIndex` +
:class:`~handbook.graph.traversal.Traversal` +
:class:`~handbook.graph.export.Exporter` -- composition, not
inheritance, so each concern stays independently testable while callers
still get one convenient object (``graph = GraphBuilder(...).build()``)
to hold onto and call ``graph.get(...)``, ``graph.related(...)``,
``graph.backlinks(...)``, ``graph.export_json()`` on directly.
"""

from __future__ import annotations

from collections.abc import Iterable

from handbook.graph.edge import Edge
from handbook.graph.exceptions import NodeNotFoundError
from handbook.graph.export import Exporter
from handbook.graph.index import GraphIndex
from handbook.graph.node import Node
from handbook.graph.traversal import Traversal
from handbook.models.enums import RelationType
from handbook.utils.slug import note_slug


class KnowledgeGraph:
    """Query surface over a built graph: lookup, relations, traversal, export."""

    def __init__(self, index: GraphIndex) -> None:
        self._index = index
        self._traversal = Traversal(index)
        self._exporter = Exporter(index)

    @property
    def index(self) -> GraphIndex:
        """The underlying :class:`~handbook.graph.index.GraphIndex`.

        Exposed so a caller can hand it straight to
        :class:`~handbook.graph.search.SearchEngine` or
        :class:`~handbook.graph.duplicates.DuplicateDetector` (or use
        the :meth:`search_engine` / :meth:`duplicate_detector`
        convenience factories below), without this class needing to
        know anything about search ranking or duplicate heuristics
        itself.
        """
        return self._index

    def __len__(self) -> int:
        return self._index.node_count()

    def __contains__(self, ref: str) -> bool:
        return self.get(ref) is not None

    # -- lookup -----------------------------------------------------------
    def get(self, ref: str) -> Node | None:
        """Look up a node by id, slug, alias, or title (in that order).

        Read-only: unlike :class:`~handbook.graph.resolver.Resolver`,
        this never creates a shadow node -- it's for a caller who just
        wants to know whether something exists, without the side effect
        of fabricating a placeholder if it doesn't.
        """
        node = self._index.get_node(ref)
        if node is not None:
            return node
        node = self._index.find_by_slug(note_slug(ref))
        if node is not None:
            return node
        matches = self._index.find_by_alias(ref)
        if matches:
            return matches[0]
        matches = self._index.find_by_title(ref)
        if matches:
            return matches[0]
        return None

    def nodes(self) -> list[Node]:
        return list(self._index.nodes())

    def edges(self) -> list[Edge]:
        return list(self._index.edges())

    def related(
        self,
        ref: str,
        *,
        relation_types: Iterable[RelationType] | None = None,
        direction: str = "both",
    ) -> list[tuple[Edge, Node]]:
        """Every edge touching ``ref``, paired with the node at its other end.

        The graph's general-purpose "what connects to this" query.
        ``direction="out"``/``"in"``/``"both"`` (default) controls which
        side of the edge ``ref`` must be on.
        """
        node = self._require(ref)
        candidates: list[Edge] = []
        if direction in ("out", "both"):
            candidates += self._index.out_edges(node.id)
        if direction in ("in", "both"):
            candidates += self._index.in_edges(node.id)

        allowed = set(relation_types) if relation_types is not None else None
        seen_edges: set[int] = set()
        pairs: list[tuple[Edge, Node]] = []
        for edge in candidates:
            if id(edge) in seen_edges:
                continue
            seen_edges.add(id(edge))
            if allowed is not None and edge.type not in allowed:
                continue
            other_id = edge.source if edge.target == node.id else edge.target
            other = self._index.get_node(other_id)
            if other is not None:
                pairs.append((edge, other))
        return pairs

    def backlinks(self, ref: str) -> list[tuple[Edge, Node]]:
        """Everything that points *at* ``ref``.

        Computed purely from graph edges -- never by re-parsing Markdown
        -- so backlinks stay correct as soon as the graph is (re)built.
        """
        return self.related(ref, direction="in")

    # -- traversal (thin delegation to Traversal) ------------------------
    def neighbors(self, ref: str, **kwargs) -> list[str]:
        return self._traversal.neighbors(self._require_id(ref), **kwargs)

    def successors(self, ref: str, **kwargs) -> list[str]:
        return self._traversal.successors(self._require_id(ref), **kwargs)

    def predecessors(self, ref: str, **kwargs) -> list[str]:
        return self._traversal.predecessors(self._require_id(ref), **kwargs)

    def reachable(self, ref: str, **kwargs) -> set[str]:
        return self._traversal.reachable(self._require_id(ref), **kwargs)

    def closure(self, ref: str, **kwargs) -> set[str]:
        return self._traversal.closure(self._require_id(ref), **kwargs)

    def shortest_path(
        self, source_ref: str, target_ref: str, **kwargs
    ) -> list[str] | None:
        return self._traversal.shortest_path(
            self._require_id(source_ref), self._require_id(target_ref), **kwargs
        )

    def topological_sort(self, **kwargs) -> list[str]:
        return self._traversal.topological_sort(**kwargs)

    def cycle_detection(self, **kwargs) -> list[list[str]]:
        return self._traversal.cycle_detection(**kwargs)

    def subgraph(self, refs: Iterable[str]) -> KnowledgeGraph:
        return self._traversal.subgraph(self._require_id(r) for r in refs)

    def _require(self, ref: str) -> Node:
        node = self.get(ref)
        if node is None:
            raise NodeNotFoundError(f"No node found for reference {ref!r}.")
        return node

    def _require_id(self, ref: str) -> str:
        return self._require(ref).id

    # -- export -----------------------------------------------------------
    def export_json(self, *, indent: int | None = 2) -> str:
        return self._exporter.to_json(indent=indent)

    def export_dot(self) -> str:
        return self._exporter.to_dot()

    def export_networkx(self) -> dict:
        return self._exporter.to_networkx_dict()

    # -- convenience factories --------------------------------------------
    def search_engine(self, **kwargs):
        """A :class:`~handbook.graph.search.SearchEngine` wired to this graph.

        A thin factory, not a reimplementation -- ``KnowledgeGraph``
        still doesn't know anything about ranking or fuzzy matching
        itself.
        """
        from handbook.graph.search import SearchEngine

        return SearchEngine(self._index, **kwargs)

    def duplicate_detector(self, **kwargs):
        """A :class:`~handbook.graph.duplicates.DuplicateDetector` wired to
        this graph. See :meth:`search_engine` for why this is a factory,
        not new logic."""
        from handbook.graph.duplicates import DuplicateDetector

        return DuplicateDetector(self._index, **kwargs)
