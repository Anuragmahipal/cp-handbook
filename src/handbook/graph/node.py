"""Node: the graph's view of a KnowledgeItem, or of an unresolved reference.

A ``Node`` is a lightweight *projection* of a
:class:`~handbook.models.base.KnowledgeItem`'s identity and
classification metadata. It deliberately never carries the item's
rendered body / free-form ``notes`` -- the graph is a derived index, not
a second copy of the vault's content, so anyone who wants the actual
prose still goes back to the KnowledgeItem (or the rendered Markdown)
for it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from handbook.utils.slug import note_slug

if TYPE_CHECKING:
    from handbook.models import KnowledgeItem

_SHADOW_PREFIX = "shadow:"


class Node(BaseModel):
    """A single vertex in the knowledge graph.

    Either a real node (backed by a ``KnowledgeItem``, ``is_shadow=False``)
    or a shadow node (``is_shadow=True``): a placeholder created because
    some :class:`~handbook.models.base.Relation` pointed at a target that
    never resolved to a real item. Shadow nodes carry no classification
    metadata beyond their title/slug, but they remain full graph
    citizens -- queryable, searchable, traversable -- so a dangling
    reference is visible instead of silently dropped.
    """

    id: str
    kind: str
    title: str
    slug: str
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_shadow: bool = False

    def matches_text(self, needle: str) -> bool:
        """Cheap case-insensitive substring check across title/aliases/tags.

        Used as a fast pre-filter ahead of :class:`~handbook.graph.search.
        SearchEngine`'s ranked scoring, and handy on its own for simple
        "does this node mention X" checks.
        """
        needle = needle.lower()
        if needle in self.title.lower():
            return True
        if any(needle in alias.lower() for alias in self.aliases):
            return True
        if any(needle in tag.lower() for tag in self.tags):
            return True
        return False

    @classmethod
    def from_item(cls, item: KnowledgeItem) -> Node:
        """Project a ``KnowledgeItem`` into its graph ``Node``."""
        difficulty = item.difficulty.value if item.difficulty is not None else None
        return cls(
            id=item.id,
            kind=item.kind,
            title=item.title,
            slug=item.slug,
            aliases=list(item.aliases),
            tags=list(item.tags),
            difficulty=difficulty,
            status=item.status.value,
        )

    @classmethod
    def shadow(cls, target: str) -> Node:
        """Build the (deterministic) shadow node for an unresolved ``target``.

        The id is derived from the target's slug so that every relation
        pointing at the same unresolved name -- however many times it's
        referenced, from however many items -- converges on one shared
        shadow node rather than minting a duplicate each time.
        """
        cleaned = target.strip()
        slug = note_slug(cleaned) or cleaned.lower()
        return cls(
            id=f"{_SHADOW_PREFIX}{slug}",
            kind="unknown",
            title=cleaned,
            slug=slug,
            is_shadow=True,
        )
