"""Traversal: pure graph-walking algorithms over a GraphIndex.

Deliberately its own class, separate from :class:`~handbook.graph.
builder.GraphBuilder` (construction) and from :class:`~handbook.graph.
graph.KnowledgeGraph` (the convenience facade) -- everything here only
ever *reads* the index, never mutates it, so these algorithms can be
reasoned about and tested independently of how the graph was built.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import TYPE_CHECKING

from handbook.graph.edge import EdgeDirection
from handbook.graph.exceptions import GraphCycleError
from handbook.graph.index import GraphIndex
from handbook.models.enums import RelationType

if TYPE_CHECKING:
    from handbook.graph.graph import KnowledgeGraph


class Traversal:
    """Neighbor queries, reachability, paths, and DAG algorithms."""

    def __init__(self, index: GraphIndex) -> None:
        self._index = index

    # -- direct neighbors ---------------------------------------------------
    def successors(
        self, node_id: str, *, relation_types: Iterable[RelationType] | None = None
    ) -> list[str]:
        """Node ids directly reachable *from* ``node_id`` in one hop.

        Includes both the target of every outgoing edge and the source
        of every incoming :attr:`~handbook.graph.edge.EdgeDirection.
        BIDIRECTIONAL` edge, since a bidirectional edge is a successor
        relationship from either endpoint's point of view.
        """
        return self._walk_one_hop(node_id, relation_types, want="successor")

    def predecessors(
        self, node_id: str, *, relation_types: Iterable[RelationType] | None = None
    ) -> list[str]:
        """Node ids that reach ``node_id`` in one hop. Mirror of :meth:`successors`."""
        return self._walk_one_hop(node_id, relation_types, want="predecessor")

    def neighbors(
        self, node_id: str, *, relation_types: Iterable[RelationType] | None = None
    ) -> list[str]:
        """The union of :meth:`successors` and :meth:`predecessors`, deduped."""
        seen: set[str] = set()
        result: list[str] = []
        for nid in self.successors(
            node_id, relation_types=relation_types
        ) + self.predecessors(node_id, relation_types=relation_types):
            if nid not in seen:
                seen.add(nid)
                result.append(nid)
        return result

    def _walk_one_hop(
        self,
        node_id: str,
        relation_types: Iterable[RelationType] | None,
        *,
        want: str,
    ) -> list[str]:
        allowed = set(relation_types) if relation_types is not None else None
        seen: set[str] = set()
        result: list[str] = []
        for edge in self._index.out_edges(node_id) + self._index.in_edges(node_id):
            if allowed is not None and edge.type not in allowed:
                continue
            other = (
                edge.successor_of(node_id)
                if want == "successor"
                else edge.predecessor_of(node_id)
            )
            if other is not None and other not in seen:
                seen.add(other)
                result.append(other)
        return result

    # -- multi-hop ------------------------------------------------------
    def reachable(
        self,
        node_id: str,
        *,
        relation_types: Iterable[RelationType] | None = None,
        max_depth: int | None = None,
    ) -> set[str]:
        """Every node reachable from ``node_id`` by following successors.

        ``node_id`` itself is never included. ``max_depth`` bounds the
        number of hops (``1`` = direct successors only); ``None`` means
        unbounded. ``relation_types`` restricts which edges may be
        followed -- e.g. ``reachable(problem_id,
        relation_types=[RelationType.PREREQUISITE])`` answers "everything
        that must be understood before this problem".
        """
        visited: set[str] = set()
        frontier = [node_id]
        depth = 0
        while frontier and (max_depth is None or depth < max_depth):
            next_frontier: list[str] = []
            for current in frontier:
                for nxt in self.successors(current, relation_types=relation_types):
                    if nxt not in visited and nxt != node_id:
                        visited.add(nxt)
                        next_frontier.append(nxt)
            frontier = next_frontier
            depth += 1
        return visited

    def closure(
        self, node_id: str, *, relation_types: Iterable[RelationType] | None = None
    ) -> set[str]:
        """The full, unbounded transitive closure of :meth:`reachable`.

        Its own name because "everything eventually reachable from here,
        period" is a distinct, common query from "what's within N hops",
        even though it's implemented as the unbounded case of
        :meth:`reachable`.
        """
        return self.reachable(node_id, relation_types=relation_types, max_depth=None)

    def shortest_path(
        self,
        source_id: str,
        target_id: str,
        *,
        relation_types: Iterable[RelationType] | None = None,
    ) -> list[str] | None:
        """The shortest (fewest-hops) path from ``source_id`` to ``target_id``.

        Returns the full list of node ids including both endpoints, or
        ``None`` if ``target_id`` isn't reachable. Unweighted BFS --
        every edge counts as one hop regardless of ``confidence``.
        """
        if source_id == target_id:
            return [source_id]

        visited = {source_id}
        parent: dict[str, str] = {}
        queue: deque[str] = deque([source_id])

        while queue:
            current = queue.popleft()
            for nxt in self.successors(current, relation_types=relation_types):
                if nxt in visited:
                    continue
                visited.add(nxt)
                parent[nxt] = current
                if nxt == target_id:
                    path = [nxt]
                    while path[-1] != source_id:
                        path.append(parent[path[-1]])
                    path.reverse()
                    return path
                queue.append(nxt)
        return None

    def subgraph(self, node_ids: Iterable[str]) -> KnowledgeGraph:
        """The induced subgraph on ``node_ids``: those nodes, plus every
        edge whose *both* endpoints are in the set.

        Returns a standalone :class:`~handbook.graph.graph.KnowledgeGraph`
        with its own index, so operating on the subgraph (search,
        further traversal, export) never touches the parent graph.
        """
        # Imported lazily: KnowledgeGraph imports GraphBuilder imports
        # this module at class-definition time, so importing it back at
        # module scope here would be circular. By call time (some caller
        # already holding a built KnowledgeGraph) every module involved
        # has finished loading, so this is safe.
        from handbook.graph.graph import KnowledgeGraph

        ids = set(node_ids)
        new_index = GraphIndex()
        for node_id in ids:
            node = self._index.get_node(node_id)
            if node is not None:
                new_index.upsert_node(node)
        for edge in self._index.edges():
            if edge.source in ids and edge.target in ids:
                new_index.add_edge(edge)
        return KnowledgeGraph(new_index)

    # -- DAG algorithms -------------------------------------------------
    def topological_sort(
        self, *, relation_types: Iterable[RelationType] | None = None
    ) -> list[str]:
        """A topological ordering of the graph's nodes.

        Only considers :attr:`~handbook.graph.edge.EdgeDirection.FORWARD`
        edges: a bidirectional edge (``similar_to``, ``related``, ...)
        describes a symmetric relationship, not a hierarchy, so including
        it would make any pair it connects trivially cyclic. Restrict
        further with ``relation_types`` (e.g. just ``PREREQUISITE``) to
        sort one specific hierarchy rather than the whole forward graph.

        The order follows literal edge direction (``source`` before
        ``target``) for every relation type alike -- see the module docs
        on :mod:`handbook.graph.edge` for why that means a
        ``PREREQUISITE`` chain comes out "dependent before its
        prerequisite", not the reverse "study order" a caller might
        expect; read the result backwards, or query ``predecessors``/
        ``successors`` directly, to get that ordering instead.

        Raises:
            GraphCycleError: if the (filtered) forward graph isn't a DAG.
        """
        adjacency = self._forward_adjacency(relation_types)
        indegree: dict[str, int] = dict.fromkeys(adjacency, 0)
        for targets in adjacency.values():
            for target in targets:
                indegree[target] = indegree.get(target, 0) + 1
                adjacency.setdefault(target, [])

        queue: deque[str] = deque(
            node for node, degree in indegree.items() if degree == 0
        )
        order: list[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for nxt in adjacency.get(node, []):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)

        if len(order) != len(indegree):
            cycles = self.cycle_detection(relation_types=relation_types)
            raise GraphCycleError(
                "Graph contains a cycle; topological_sort requires a DAG.",
                cycle=cycles[0] if cycles else None,
            )
        return order

    def cycle_detection(
        self, *, relation_types: Iterable[RelationType] | None = None
    ) -> list[list[str]]:
        """Every distinct cycle in the forward graph (see
        :meth:`topological_sort` on why bidirectional edges are excluded).

        Returns a list of cycles, each a list of node ids where the first
        id is repeated at the end (e.g. ``["a", "b", "c", "a"]``). Empty
        if the (filtered) forward graph is a DAG.
        """
        adjacency = self._forward_adjacency(relation_types)
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = dict.fromkeys(adjacency, WHITE)
        cycles: list[list[str]] = []
        path: list[str] = []

        def visit(node: str) -> None:
            color[node] = GRAY
            path.append(node)
            for nxt in adjacency.get(node, []):
                state = color.get(nxt, WHITE)
                if state == WHITE:
                    visit(nxt)
                elif state == GRAY:
                    start = path.index(nxt)
                    cycles.append(path[start:] + [nxt])
            path.pop()
            color[node] = BLACK

        for node in list(adjacency):
            if color[node] == WHITE:
                visit(node)
        return cycles

    def _forward_adjacency(
        self, relation_types: Iterable[RelationType] | None
    ) -> dict[str, list[str]]:
        allowed = set(relation_types) if relation_types is not None else None
        adjacency: dict[str, list[str]] = {
            node_id: [] for node_id in self._index.node_ids()
        }
        for edge in self._index.edges():
            if edge.direction is not EdgeDirection.FORWARD:
                continue
            if allowed is not None and edge.type not in allowed:
                continue
            adjacency.setdefault(edge.source, []).append(edge.target)
        return adjacency
