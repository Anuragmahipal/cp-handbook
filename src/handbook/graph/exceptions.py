"""Exception hierarchy for the knowledge graph layer.

Every error raised anywhere in :mod:`handbook.graph` is a
:class:`GraphError`, itself a :class:`~handbook.exceptions.HandbookError`,
so callers can catch broadly (``except HandbookError``), narrowly
(``except GraphCycleError``), or at the graph-layer boundary
(``except GraphError``) depending on what they're doing.
"""

from __future__ import annotations

from handbook.exceptions import HandbookError


class GraphError(HandbookError):
    """Base class for every graph-layer error."""


class NodeNotFoundError(GraphError):
    """Raised by read-only lookups that refuse to fall back to a shadow node.

    :meth:`~handbook.graph.graph.KnowledgeGraph.get` and friends raise this
    for a reference that resolves to nothing, rather than silently
    returning ``None`` deep inside a call chain. Contrast with
    :class:`~handbook.graph.resolver.Resolver`, which is allowed to
    *create* a shadow node instead of failing -- that distinction is the
    difference between "resolve this relation, permissively" (graph
    construction) and "does this exist" (a caller's direct query).
    """


class GraphCycleError(GraphError):
    """Raised when an operation that requires a DAG finds a cycle.

    ``cycle``, if known, is one concrete offending cycle (a list of node
    ids, first id repeated at the end) -- enough for a caller to point a
    user at the exact loop without re-running cycle detection themselves.
    """

    def __init__(self, message: str, cycle: list[str] | None = None) -> None:
        super().__init__(message)
        self.cycle: list[str] = cycle or []
