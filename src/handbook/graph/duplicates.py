"""DuplicateDetector: finds candidate duplicates in a graph.

Every check in this module is exact-match or cheap string similarity --
nothing here understands *meaning*. Semantic duplicate detection (two
problems that are the same idea under different names) is intentionally
out of scope for this chunk; ``extra_detectors`` is the seam a later
embeddings-based detector plugs into without this class ever changing.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from handbook.graph.index import GraphIndex
from handbook.models.enums import RelationType

_DEFAULT_NEAR_DUPLICATE_THRESHOLD = 0.87


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    """A set of node ids flagged as duplicates for some ``reason``."""

    reason: str
    node_ids: list[str]
    detail: str = ""


@dataclass(frozen=True, slots=True)
class DuplicateEdgeGroup:
    """More than one edge sharing the same ``(source, target, type)``."""

    source: str
    target: str
    type: RelationType
    count: int


@dataclass(frozen=True, slots=True)
class DuplicateReport:
    """The full result of :meth:`DuplicateDetector.find_duplicates`."""

    duplicate_titles: list[DuplicateGroup]
    duplicate_aliases: list[DuplicateGroup]
    near_duplicate_names: list[DuplicateGroup]
    duplicate_edges: list[DuplicateEdgeGroup]
    extra: list[DuplicateGroup] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.duplicate_titles
            or self.duplicate_aliases
            or self.near_duplicate_names
            or self.duplicate_edges
            or self.extra
        )


ExtraDetector = Callable[[GraphIndex], list[DuplicateGroup]]


class DuplicateDetector:
    """Modular duplicate detection: titles, aliases, near-duplicate names,
    and duplicate edges, plus a pluggable hook for anything else.
    """

    def __init__(
        self,
        index: GraphIndex,
        *,
        near_duplicate_threshold: float = _DEFAULT_NEAR_DUPLICATE_THRESHOLD,
        extra_detectors: Sequence[ExtraDetector] = (),
    ) -> None:
        self._index = index
        self._threshold = near_duplicate_threshold
        self._extra_detectors = list(extra_detectors)

    def find_duplicate_titles(self) -> list[DuplicateGroup]:
        """Two or more (non-shadow) nodes with the exact same title."""
        by_title: dict[str, list[str]] = {}
        for node in self._index.nodes():
            if node.is_shadow:
                continue
            by_title.setdefault(node.title.strip().lower(), []).append(node.id)
        return [
            DuplicateGroup(reason="duplicate_title", node_ids=ids, detail=title)
            for title, ids in by_title.items()
            if len(ids) > 1
        ]

    def find_duplicate_aliases(self) -> list[DuplicateGroup]:
        """An alias (or title) shared by more than one node.

        Checks aliases against *both* other aliases and other titles,
        since ``Node.aliases`` and ``Node.title`` share one namespace as
        far as resolution is concerned -- an alias that collides with
        someone else's title is just as ambiguous as two nodes sharing
        an alias.
        """
        owners: dict[str, list[str]] = {}
        for node in self._index.nodes():
            if node.is_shadow:
                continue
            keys = {node.title.strip().lower()}
            keys.update(alias.strip().lower() for alias in node.aliases)
            for key in keys:
                owners.setdefault(key, []).append(node.id)

        groups = []
        for key, ids in owners.items():
            unique_ids = list(dict.fromkeys(ids))
            if len(unique_ids) > 1:
                groups.append(
                    DuplicateGroup(
                        reason="duplicate_alias", node_ids=unique_ids, detail=key
                    )
                )
        return groups

    def find_near_duplicate_names(self) -> list[DuplicateGroup]:
        """Pairs of distinct titles similar enough to plausibly be the same item.

        O(n^2) over non-shadow nodes -- fine for the local-vault scale
        this package targets; not intended for a corpus of thousands of
        items.
        """
        nodes = [node for node in self._index.nodes() if not node.is_shadow]
        groups: list[DuplicateGroup] = []
        for i, a in enumerate(nodes):
            a_title = a.title.strip().lower()
            for b in nodes[i + 1 :]:
                b_title = b.title.strip().lower()
                if a_title == b_title:
                    continue  # exact duplicates are find_duplicate_titles()'s job
                ratio = SequenceMatcher(None, a_title, b_title).ratio()
                if ratio >= self._threshold:
                    groups.append(
                        DuplicateGroup(
                            reason="near_duplicate_name",
                            node_ids=[a.id, b.id],
                            detail=f"similarity={ratio:.2f}",
                        )
                    )
        return groups

    def find_duplicate_edges(self) -> list[DuplicateEdgeGroup]:
        """More than one edge sharing the same source, target, and type."""
        counts: dict[tuple[str, str, RelationType], int] = {}
        for edge in self._index.edges():
            key = (edge.source, edge.target, edge.type)
            counts[key] = counts.get(key, 0) + 1
        return [
            DuplicateEdgeGroup(source=source, target=target, type=rel_type, count=count)
            for (source, target, rel_type), count in counts.items()
            if count > 1
        ]

    def find_duplicates(self) -> DuplicateReport:
        """Run every built-in check, plus any ``extra_detectors``."""
        extra: list[DuplicateGroup] = []
        for detector in self._extra_detectors:
            extra.extend(detector(self._index))
        return DuplicateReport(
            duplicate_titles=self.find_duplicate_titles(),
            duplicate_aliases=self.find_duplicate_aliases(),
            near_duplicate_names=self.find_near_duplicate_names(),
            duplicate_edges=self.find_duplicate_edges(),
            extra=extra,
        )
