"""Edge: a typed, directed connection between two nodes.

Edges originate from :class:`~handbook.models.base.Relation` objects
(see :class:`~handbook.graph.builder.GraphBuilder`), but the graph layer
adds what a bare ``Relation`` doesn't need to carry: which two node ids
it actually connects, how confidently, where it came from, and whether
the graph invented it itself. Multiple edges between the same pair of
nodes are supported -- edges are stored as a list, never deduplicated
into a single mapping -- since two items can legitimately be connected
more than one way (or the same way, authored twice; see
:class:`~handbook.graph.duplicates.DuplicateDetector`).

A note on direction and ``PREREQUISITE`` specifically
-------------------------------------------------------
``edge.source`` is always the item that *declared* the relation, and
``edge.target`` is always what it points at -- edges follow authored
direction literally, the same for every ``RelationType``. This matters
for ``PREREQUISITE``: ``Problem(prerequisites=["Binary Search"])``
produces an edge ``problem -> binary_search``, i.e. the edge points from
the dependent item to the thing it depends on -- the reverse of the
"prerequisite flows into what it unlocks" order you'd want for a study
plan. That inversion is intentional: this package stays a generic,
relation-type-agnostic graph (``topological_sort()`` orders by literal
edge direction, full stop). Interpreting ``PREREQUISITE`` edges as a
"what must I learn first" ordering is exactly the kind of relation-
type-specific semantics a future learning-path/recommendation feature
should add on top -- by reading ``predecessors(x, relation_types=
[RelationType.PREREQUISITE])`` for "what depends on x" or ``successors``
for "what x depends on" -- not something this layer bakes in.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from handbook.models.enums import RelationType


class EdgeDirection(StrEnum):
    """Whether an edge is meaningful one-way or both ways for traversal."""

    FORWARD = "forward"
    """Meaningful only source -> target (``prerequisite``, ``uses``,
    ``contains``, ...)."""

    BIDIRECTIONAL = "bidirectional"
    """Symmetric: traversal treats target -> source as equally valid
    (``similar_to``, ``related``, ``contrasts_with``)."""


_BIDIRECTIONAL_TYPES = frozenset(
    {
        RelationType.SIMILAR_TO,
        RelationType.RELATED,
        RelationType.CONTRASTS_WITH,
    }
)


def default_direction(relation_type: RelationType) -> EdgeDirection:
    """The sensible default :class:`EdgeDirection` for a ``RelationType``.

    A handful of relation types describe an inherently symmetric
    relationship rather than a directed one; everything else defaults to
    forward. Callers building an ``Edge`` directly are free to override
    this.
    """
    if relation_type in _BIDIRECTIONAL_TYPES:
        return EdgeDirection.BIDIRECTIONAL
    return EdgeDirection.FORWARD


class Edge(BaseModel):
    """A single directed (or bidirectional) connection between two nodes."""

    source: str
    target: str
    type: RelationType
    direction: EdgeDirection = EdgeDirection.FORWARD
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: str = ""
    """Where this edge came from, e.g. ``"field:algorithms"`` for an edge
    derived straight from an authored ``Relation``, or
    ``"inferred:something"`` for one the graph invented itself."""
    notes: str = ""
    """Copied from the originating ``Relation.note``, if any."""
    derived: bool = False
    """True for edges the graph invented itself (e.g. a future inverse-
    relation pass) rather than one that traces back to an authored
    ``Relation``."""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def endpoints(self) -> tuple[str, str]:
        """The ``(source, target)`` pair, as authored."""
        return (self.source, self.target)

    def successor_of(self, node_id: str) -> str | None:
        """The node this edge leads *to*, seen from ``node_id``.

        ``node_id`` must be one of this edge's endpoints. Returns the
        far end if ``node_id`` is the source (any direction), or if
        ``node_id`` is the target of a :attr:`EdgeDirection.BIDIRECTIONAL`
        edge. Returns ``None`` otherwise (e.g. ``node_id`` is the target
        of a plain forward edge -- that's a *predecessor* relationship,
        see :meth:`predecessor_of`).
        """
        if node_id == self.source:
            return self.target
        if node_id == self.target and self.direction is EdgeDirection.BIDIRECTIONAL:
            return self.source
        return None

    def predecessor_of(self, node_id: str) -> str | None:
        """The node this edge leads *from*, seen from ``node_id``.

        Mirror image of :meth:`successor_of`: the far end if ``node_id``
        is the target (any direction), or if ``node_id`` is the source of
        a bidirectional edge.
        """
        if node_id == self.target:
            return self.source
        if node_id == self.source and self.direction is EdgeDirection.BIDIRECTIONAL:
            return self.target
        return None
