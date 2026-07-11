"""Resolver: turns a free-form reference string into a concrete node.

``Relation.target`` (see :class:`~handbook.models.base.Relation`) is
deliberately just a string -- an id, a title, or an alias -- because the
knowledge model layer has no query of its own. Resolving that string
into an actual node is exactly the job this class exists for.
"""

from __future__ import annotations

from handbook.graph.index import GraphIndex
from handbook.graph.node import Node
from handbook.utils.slug import note_slug


class Resolver:
    """Resolves a raw reference to a :class:`~handbook.graph.node.Node`.

    Resolution is tried in this order, first match wins:

    1. exact node id
    2. exact slug
    3. alias (case-insensitive)
    4. title (case-insensitive)

    If a title or alias matches more than one node, the first one
    registered wins; that collision is exactly what
    :class:`~handbook.graph.duplicates.DuplicateDetector` surfaces, so
    the ambiguity is visible rather than silently resolved away.

    Anything matching none of the above becomes (or reuses) a
    :meth:`~handbook.graph.node.Node.shadow` node, so a dangling
    reference stays queryable instead of disappearing. This permissive
    behavior is what distinguishes ``Resolver`` from a read-only lookup
    like :meth:`~handbook.graph.graph.KnowledgeGraph.get`, which raises
    rather than fabricating a node.
    """

    def __init__(self, index: GraphIndex) -> None:
        self._index = index

    def resolve(self, target: str) -> Node:
        """Resolve ``target``, creating a shadow node as a last resort."""
        cleaned = target.strip()

        node = self._index.get_node(cleaned)
        if node is not None:
            return node

        node = self._index.find_by_slug(note_slug(cleaned))
        if node is not None:
            return node

        matches = self._index.find_by_alias(cleaned)
        if matches:
            return matches[0]

        matches = self._index.find_by_title(cleaned)
        if matches:
            return matches[0]

        return self._index.get_or_create_shadow(cleaned)

    def resolve_id(self, target: str) -> str:
        """Convenience wrapper over :meth:`resolve` returning just the id."""
        return self.resolve(target).id
