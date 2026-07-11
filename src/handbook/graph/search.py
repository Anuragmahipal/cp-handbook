"""SearchEngine: ranked search over a graph's nodes.

Built purely on top of :class:`~handbook.graph.index.GraphIndex` -- no
filesystem or rendering dependency -- so it behaves identically whether
the graph came from a real vault or from a handful of items in a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from handbook.graph.index import GraphIndex
from handbook.graph.node import Node
from handbook.graph.resolver import Resolver
from handbook.models.enums import RelationType

_FUZZY_THRESHOLD = 0.6


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One ranked hit: the node, its score, and which field matched best."""

    node: Node
    score: float
    matched_field: str


class SearchEngine:
    """Title/alias/tag/metadata search, plus dedicated prefix and relation queries."""

    def __init__(self, index: GraphIndex) -> None:
        self._index = index

    def search(
        self,
        query: str,
        *,
        kind: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        include_shadow: bool = False,
        limit: int = 20,
    ) -> list[SearchResult]:
        """Ranked full-text search across title, aliases, tags, and metadata.

        ``kind``/``status``/``tags`` filter the candidate set before
        scoring (an exact match, not part of the ranking); the ranking
        itself favors exact title/alias matches, then prefix matches,
        then substring matches, then fuzzy (edit-distance) matches, in
        that order. Shadow nodes are excluded unless
        ``include_shadow=True``, since a dangling reference is rarely a
        useful search result.
        """
        cleaned = query.strip()
        if not cleaned:
            return []
        needle = cleaned.lower()
        wanted_tags = {t.lower() for t in tags} if tags else None

        results: list[SearchResult] = []
        for node in self._index.nodes():
            if not include_shadow and node.is_shadow:
                continue
            if kind is not None and node.kind != kind:
                continue
            if status is not None and node.status != status:
                continue
            if wanted_tags is not None and wanted_tags.isdisjoint(
                t.lower() for t in node.tags
            ):
                continue
            score, field = self._score(node, needle)
            if score > 0:
                results.append(
                    SearchResult(node=node, score=score, matched_field=field)
                )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    @staticmethod
    def _score(node: Node, needle: str) -> tuple[float, str]:
        title_lower = node.title.lower()

        if title_lower == needle:
            return 100.0, "title"
        for alias in node.aliases:
            if alias.lower() == needle:
                return 95.0, "aliases"
        if title_lower.startswith(needle):
            return 80.0, "title"
        for alias in node.aliases:
            if alias.lower().startswith(needle):
                return 75.0, "aliases"
        if needle in title_lower:
            return 60.0, "title"
        for alias in node.aliases:
            if needle in alias.lower():
                return 55.0, "aliases"
        for tag in node.tags:
            tag_lower = tag.lower()
            if needle == tag_lower:
                return 50.0, "tags"
            if needle in tag_lower:
                return 40.0, "tags"
        for key, value in node.metadata.items():
            if needle in str(value).lower():
                return 20.0, f"metadata.{key}"

        ratio = SequenceMatcher(None, needle, title_lower).ratio()
        if ratio >= _FUZZY_THRESHOLD:
            return ratio * 50.0, "title (fuzzy)"
        return 0.0, ""

    def prefix(self, prefix: str, *, limit: int = 20) -> list[Node]:
        """Dedicated prefix search over title/aliases, for autocomplete-style UX."""
        cleaned = prefix.strip().lower()
        if not cleaned:
            return []
        matches: list[Node] = []
        for node in self._index.nodes():
            if node.is_shadow:
                continue
            if node.title.lower().startswith(cleaned) or any(
                alias.lower().startswith(cleaned) for alias in node.aliases
            ):
                matches.append(node)
                if len(matches) >= limit:
                    break
        return matches

    def by_relation(
        self,
        relation_type: RelationType,
        *,
        target: str | None = None,
        direction: Literal["out", "in", "both"] = "out",
        limit: int | None = None,
    ) -> list[Node]:
        """ "Relation queries": nodes connected via ``relation_type``.

        With ``target`` given and ``direction="out"`` (the default):
        every node with a ``relation_type`` edge *pointing at* ``target``
        -- e.g. ``by_relation(RelationType.USES, target="Binary
        Lifting")`` answers "what uses Binary Lifting". ``direction=
        "in"`` instead returns what ``target`` itself points at via that
        relation type. ``target=None`` ignores the target and returns
        every node on the requested side of *any* edge of this type.
        ``target`` may be an id, slug, alias, or title -- it's resolved
        the same way a ``Relation.target`` would be, including falling
        back to a shadow node if it doesn't match anything real.
        """
        resolved_target = (
            Resolver(self._index).resolve_id(target) if target is not None else None
        )

        seen: set[str] = set()
        matches: list[Node] = []
        for edge in self._index.edges():
            if edge.type != relation_type:
                continue
            if direction in ("out", "both") and (
                resolved_target is None or edge.target == resolved_target
            ):
                node = self._index.get_node(edge.source)
                if node is not None and node.id not in seen:
                    seen.add(node.id)
                    matches.append(node)
            if direction in ("in", "both") and (
                resolved_target is None or edge.source == resolved_target
            ):
                node = self._index.get_node(edge.target)
                if node is not None and node.id not in seen:
                    seen.add(node.id)
                    matches.append(node)

        return matches[:limit] if limit is not None else matches
