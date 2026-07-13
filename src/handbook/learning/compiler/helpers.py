"""Shared, read-only helpers every concrete compiler builds on.

Every function here does one small, mechanical thing -- deriving a
stable id, building one "Related X" section from graph edges, wiring
up a default ``MemoryAnchor``/``ReviewCue`` pair -- so that
``AlgorithmCompiler``/``ProblemCompiler``/``PatternCompiler``/
``MistakeCompiler``/``ContestCompiler`` each read as "the fields this
knowledge type actually has, mapped onto the LIR" rather than five
copies of the same graph-walking and id-plumbing code.

Two design decisions worth calling out up front:

**Every id this package mints is deterministic, not random.** Every
LIR ``Identified`` defaults to a random ``uuid4()`` id when a caller
doesn't pass one explicitly (see ``handbook.learning.versioning``) --
correct for hand-authored content, wrong for a *compiler*, where
recompiling the same ``KnowledgeItem`` (the same note, re-synced through
``cp-handbook sync`` a second time) should produce byte-identical
output, not a new object graph with new ids every run. :func:`stable_id`
derives a ``uuid5`` from ``(item.id, qualifier)`` instead, so every
block/section/anchor a compiler builds has a stable, reproducible id as
long as the source item's own id and the compiler's internal qualifier
strings don't change. See ``docs/ARCHITECTURE_NOTES_COMPILER.md`` for
why this matters for storage idempotency and for a future
review-scheduling engine that will want to match a ``ReviewCue`` back
to the same anchor across resyncs.

**Timestamps are copied from the source item, never generated fresh.**
``Page``/``Section`` (both ``Revisable``) default ``created_at``/
``updated_at`` to ``datetime.now()`` -- again, correct for hand-authored
content, wrong for a compiler, where the same determinism requirement
applies. :func:`timestamps` returns the source item's own
``created_at``/``updated_at`` for every ``Revisable`` the compiler
constructs.

**A ``Section``'s cross-references are validated the moment it's
constructed** (see ``handbook.learning.page.Section``), and every LIR
model is frozen -- so a ``MemoryAnchor`` must be built, and its
``target_id`` resolved, *before* the ``Section`` it belongs to, never
patched on afterward via ``model_copy`` (which does not re-validate).
:func:`section_with_anchor` is the one place that ordering is handled,
so no concrete compiler has to get it right five separate times.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from uuid import UUID, uuid5

from handbook.graph import Edge, Node
from handbook.learning.blocks import Block, Callout, TextBlock
from handbook.learning.enums import AnchorType, CalloutKind, Emphasis, TextRole
from handbook.learning.page import Page, PageMetadata, Section
from handbook.learning.review import MemoryAnchor, ReviewCue
from handbook.learning.richtext import RichText, Span
from handbook.models.base import KnowledgeItem

from handbook.learning.compiler.context import CompilationContext

_ID_NAMESPACE = UUID("6f5f6d9a-9b1c-4b7e-8a2f-2f2a3f7e5c11")
"""Fixed namespace for this package's uuid5-derived ids. Any constant
UUID works -- what matters is that it never changes, since changing it
would silently reassign every id this package has ever produced."""


def stable_id(item: KnowledgeItem, qualifier: str) -> str:
    """A deterministic id for one piece of ``item``'s compiled output.

    ``qualifier`` should be unique *within one compiled Page* (by
    convention: ``"section:<name>"``, ``"block:<name>"``,
    ``"anchor:<name>"``, ``"cue:<name>"``) -- uniqueness across
    different items is already guaranteed by ``item.id`` being part of
    the hash input.
    """
    return str(uuid5(_ID_NAMESPACE, f"{item.id}:{qualifier}"))


def timestamps(item: KnowledgeItem) -> dict[str, object]:
    """``created_at``/``updated_at`` overrides for a ``Revisable`` this
    compiler is about to construct, copied from ``item`` -- see the
    module docstring for why these are never left to default.
    """
    return {"created_at": item.created_at, "updated_at": item.updated_at}


# -- page / section construction ---------------------------------------------


def base_metadata(
    item: KnowledgeItem,
    *,
    source_kind: str,
    summary: str = "",
    estimated_minutes: int | None = None,
    difficulty_override: str | None = None,
) -> PageMetadata:
    """``PageMetadata`` built from the fields every ``KnowledgeItem``
    shares (title, tags, difficulty), plus whatever a concrete compiler
    can only derive itself (``summary``, ``estimated_minutes``).

    ``difficulty_override`` lets a compiler substitute something more
    informative than the formal ``Difficulty`` enum when it's unset --
    e.g. ``ProblemCompiler`` falls back to the raw Codeforces rating,
    the same convention ``examples/problem_page.json`` uses.
    """
    difficulty = difficulty_override
    if difficulty is None and item.difficulty is not None:
        difficulty = item.difficulty.value
    return PageMetadata(
        title=item.title,
        summary=summary,
        tags=tuple(item.tags),
        source_kind=source_kind,
        difficulty=difficulty,
        estimated_minutes=estimated_minutes,
    )


def build_page(item: KnowledgeItem, metadata: PageMetadata, sections: Sequence[Section]) -> Page:
    """The top-level ``Page`` for one compiled item: a deterministic id,
    ``item``'s own timestamps, and the sections a concrete compiler
    already assembled.
    """
    return Page(
        id=stable_id(item, "page"),
        metadata=metadata,
        sections=tuple(sections),
        **timestamps(item),
    )


def plain_section(
    item: KnowledgeItem, qualifier: str, heading: str, blocks: Sequence[Block]
) -> Section:
    """A ``Section`` with no memory anchor -- most sections a compiler
    builds (prose, callouts, related-item lists) don't need one; see
    :func:`section_with_anchor` for the ones that do.
    """
    return Section(
        id=stable_id(item, f"section:{qualifier}"),
        heading=RichText.plain(heading),
        blocks=tuple(blocks),
        **timestamps(item),
    )


def section_with_anchor(
    item: KnowledgeItem,
    qualifier: str,
    heading: str,
    blocks: Sequence[Block],
    *,
    prompt_text: str,
    target_id: str | None = None,
    anchor_type: AnchorType = AnchorType.QUESTION,
) -> Section:
    """A ``Section`` with a default ``MemoryAnchor``/``ReviewCue`` (see
    :func:`default_anchor_and_cue`) already wired in.

    ``target_id`` is the id of one of ``blocks`` to anchor to; leave it
    ``None`` to anchor the whole section (its own id) -- the same
    pattern ``examples/mistake_page.json``'s "Prevention" section uses
    for a callout-only section with nothing more specific to point at.
    """
    section_id = stable_id(item, f"section:{qualifier}")
    resolved_target = target_id if target_id is not None else section_id
    anchor, cue = default_anchor_and_cue(
        item, qualifier, resolved_target, prompt_text, anchor_type=anchor_type
    )
    return Section(
        id=section_id,
        heading=RichText.plain(heading),
        blocks=tuple(blocks),
        memory_anchors=(anchor,),
        review_cues=(cue,),
        **timestamps(item),
    )


# -- text helpers -------------------------------------------------------------


def plain_text_block(
    item: KnowledgeItem, qualifier: str, text: str, *, role: TextRole = TextRole.BODY
) -> TextBlock:
    """A single-paragraph ``TextBlock`` with a deterministic id."""
    return TextBlock(id=stable_id(item, qualifier), role=role, content=RichText.plain(text))


def bulleted_callout(
    item: KnowledgeItem,
    qualifier: str,
    *,
    kind: CalloutKind,
    title: str,
    lines: Sequence[str],
) -> Callout:
    """A ``Callout`` whose body is one ``TextBlock`` per line in
    ``lines`` -- the LIR's nearest equivalent to a bullet list (see
    ``handbook.learning.blocks``: ``Callout.body`` is a small, finite
    sequence of ``TextBlock``/``CodeBlock``, not a recursive list type
    of its own).
    """
    body = tuple(
        TextBlock(id=stable_id(item, f"{qualifier}:{i}"), content=RichText.plain(line))
        for i, line in enumerate(lines)
    )
    return Callout(id=stable_id(item, qualifier), kind=kind, title=title, body=body)


# -- graph-derived "related X" sections ---------------------------------------


def _edge_matches(edge: Edge, *, field_name: str) -> bool:
    """Does ``edge`` trace back to the authored relation field
    ``field_name``?

    Filters on ``Edge.provenance`` (``"field:<name>"``, set by
    ``GraphBuilder``) rather than ``Edge.type`` -- several unrelated
    fields across different knowledge types share the same default
    ``RelationType`` (both ``Problem.algorithms`` and
    ``Problem.patterns`` default to ``USES``; ``Mistake.
    related_algorithms`` and ``Pattern.related_algorithms`` are
    literally the same field name on different classes). Provenance is
    the one signal precise enough to isolate "just this field" without
    this package inventing a second relation taxonomy of its own --
    exactly the "consume the graph, don't duplicate its logic"
    constraint this whole package is built under.
    """
    return edge.provenance == f"field:{field_name}"


def related_pairs(
    context: CompilationContext,
    item: KnowledgeItem,
    *,
    field_name: str,
    direction: str,
    other_kind: str | None = None,
) -> list[tuple[Edge, Node]]:
    """Every ``(edge, node)`` pair this compiler should show for one
    "Related X" section.

    Args:
        field_name: The authored relation field to isolate (see
            :func:`_edge_matches`).
        direction: ``"out"`` for a field authored *on* ``item`` itself
            (e.g. ``Algorithm.related_problems``); ``"in"`` for a
            backlink -- content that names ``item`` from *another*
            item's own field (e.g. every ``Mistake`` whose
            ``related_algorithms`` points back at this algorithm).
        other_kind: When set, keep only pairs whose far-side node is of
            this ``Node.kind`` (e.g. ``"mistake"``) -- necessary
            because a few field names are reused across knowledge
            types (see :func:`_edge_matches`), so an incoming
            ``"field:related_algorithms"`` edge could originate from
            either a ``Mistake`` or a ``Pattern``.

    Returns an empty list -- never raises -- if ``item`` isn't in
    ``context.graph`` at all (e.g. a freshly-constructed item being
    compiled speculatively, before any ``GraphBuilder`` pass has ever
    seen it). A compiler with no graph data for this item simply
    produces a page with that "Related X" section omitted, exactly as
    if the item had no relations of that kind at all.
    """
    if context.graph.get(item.id) is None:
        return []
    pairs = context.graph.related(item.id, direction=direction)
    matches = [
        (edge, node) for edge, node in pairs if _edge_matches(edge, field_name=field_name)
    ]
    if other_kind is not None:
        matches = [(edge, node) for edge, node in matches if node.kind == other_kind]
    return matches


def merge_pairs(*groups: Sequence[tuple[Edge, Node]]) -> list[tuple[Edge, Node]]:
    """Combine several ``related_pairs()`` results, deduping by the
    far-side node's id (first occurrence wins) while preserving order.

    Used when two different authored fields describe the same
    real-world relationship from opposite ends -- e.g. an algorithm's
    own ``related_problems`` and a problem's own ``algorithms`` both
    describe "this problem uses this algorithm"; a reader looking at
    the algorithm's "Related Problems" section shouldn't see the same
    problem listed twice just because both sides happened to author
    the link.
    """
    seen: set[str] = set()
    merged: list[tuple[Edge, Node]] = []
    for group in groups:
        for edge, node in group:
            if node.id in seen:
                continue
            seen.add(node.id)
            merged.append((edge, node))
    return merged


def linked_list_block(
    item: KnowledgeItem, qualifier: str, pairs: Iterable[tuple[Edge, Node]]
) -> TextBlock:
    """One ``TextBlock`` listing every node in ``pairs`` as a
    comma-separated run of ``RichText`` spans, each carrying
    ``link_target=node.id`` -- the same "reference as structured data,
    not a Markdown link" idiom already used by
    ``examples/mistake_page.json``'s "Related Problems" section (see
    ``handbook.learning.richtext.Span.link_target``: this package does
    not resolve the reference to actual content, it only carries it,
    same as ``Relation.target`` does one layer down).

    A relation's ``note`` (see ``handbook.models.base.Relation.note``),
    when present, is appended in parentheses -- the one piece of
    authored prose this section reuses rather than re-deriving, since
    it's already exactly the short, factual context the LIR calls for.
    """
    spans: list[Span] = []
    for i, (edge, node) in enumerate(pairs):
        if i > 0:
            spans.append(Span(text=", "))
        spans.append(Span(text=node.title, emphasis=(Emphasis.STRONG,), link_target=node.id))
        if edge.notes:
            spans.append(Span(text=f" ({edge.notes})"))
    return TextBlock(id=stable_id(item, qualifier), content=RichText(spans=tuple(spans)))


def related_section(
    item: KnowledgeItem,
    qualifier: str,
    heading: str,
    pairs: Sequence[tuple[Edge, Node]],
) -> Section | None:
    """A whole ``Section`` for one "Related X" list, or ``None`` if
    ``pairs`` is empty -- an empty relation is simply not shown, rather
    than rendered as an empty or placeholder section (a caller that
    wants to know a section was skipped for lack of content reads
    ``CompilationResult.warnings`` instead).
    """
    if not pairs:
        return None
    block = linked_list_block(item, f"block:{qualifier}", pairs)
    return plain_section(item, qualifier, heading, (block,))


def prerequisites_section(context: CompilationContext, item: KnowledgeItem) -> Section | None:
    """The "Prerequisites" section every knowledge type shares, since
    ``prerequisites`` is a base ``KnowledgeItem`` field (see
    ``handbook.models.base.KnowledgeItem``) -- one shared implementation
    instead of five near-identical copies across the concrete
    compilers.
    """
    pairs = related_pairs(context, item, field_name="prerequisites", direction="out")
    return related_section(item, "prerequisites", "Prerequisites", pairs)


# -- default memory anchor / review cue ---------------------------------------


def default_anchor_and_cue(
    item: KnowledgeItem,
    qualifier: str,
    target_id: str,
    prompt_text: str,
    *,
    anchor_type: AnchorType = AnchorType.QUESTION,
) -> tuple[MemoryAnchor, ReviewCue]:
    """A template-driven default ``MemoryAnchor`` + brand-new
    ``ReviewCue``, per the chunk brief: content is a short,
    deterministic prompt (never AI-generated); state starts at
    ``ReviewStatus.NEW``/``strength=0``/no review history, which are
    already every field's own default, so nothing needs overriding here.
    Improving on these defaults (spaced-repetition scheduling, richer
    prompts) is explicitly future work -- see
    ``docs/ARCHITECTURE_NOTES_COMPILER.md``.
    """
    anchor = MemoryAnchor(
        id=stable_id(item, f"anchor:{qualifier}"),
        target_id=target_id,
        prompt=RichText.plain(prompt_text),
        anchor_type=anchor_type,
    )
    cue = ReviewCue(id=stable_id(item, f"cue:{qualifier}"), anchor_id=anchor.id)
    return anchor, cue


AnchorSpec = tuple[str, str, str]
"""``(qualifier, target_id, prompt_text)`` -- which already-built section
(by its own qualifier) should carry the default anchor, which block/
section id within it the anchor targets, and the prompt text."""

SectionSpec = tuple[str, str, Sequence[Block]]
"""``(qualifier, heading, blocks)`` -- everything :func:`plain_section`/
:func:`section_with_anchor` need, without committing to which one gets
called until :func:`sections_with_optional_anchor` decides."""


def sections_with_optional_anchor(
    item: KnowledgeItem, specs: Sequence[SectionSpec], anchor: AnchorSpec | None
) -> list[Section]:
    """Build one ``Section`` per entry in ``specs``, in order -- all
    plain, except the one entry whose qualifier matches ``anchor[0]``
    (if any), which gets a default ``MemoryAnchor``/``ReviewCue``
    attached via :func:`section_with_anchor` instead.

    This is what lets each concrete compiler pick exactly one "primary"
    piece of content to anchor a review prompt to (preferring, say, a
    worked implementation over a bare intuition blurb when both exist)
    without every compiler re-deriving the same
    "build sections, then splice an anchor into whichever one won"
    control flow by hand.

    If ``anchor`` is given but its qualifier doesn't match any entry in
    ``specs``, the anchor is silently dropped -- that shape only arises
    from a compiler bug (picking an anchor target from a section it
    never actually built), not from any legitimate sparse-item state,
    so it deliberately doesn't raise and doesn't need its own test path
    beyond "every compiler's own anchor qualifier is one of its own
    section qualifiers", which the compiler-specific tests already
    cover per item shape.
    """
    anchor_qualifier = anchor[0] if anchor is not None else None
    sections: list[Section] = []
    for qualifier, heading, blocks in specs:
        if anchor is not None and qualifier == anchor_qualifier:
            _, target_id, prompt_text = anchor
            sections.append(
                section_with_anchor(
                    item,
                    qualifier,
                    heading,
                    blocks,
                    prompt_text=prompt_text,
                    target_id=target_id,
                )
            )
        else:
            sections.append(plain_section(item, qualifier, heading, blocks))
    return sections


def pick_anchor(*candidates: tuple[str, str | None, str]) -> AnchorSpec | None:
    """The first candidate whose target id is populated, as an
    :data:`AnchorSpec`, or ``None`` if every candidate was unavailable.

    Args:
        candidates: ``(qualifier, target_id_or_none, prompt_text)``
            triples, in priority order -- e.g. a compiler might prefer
            anchoring to a code implementation over a bare intuition
            paragraph when both exist.
    """
    for qualifier, target_id, prompt_text in candidates:
        if target_id is not None:
            return qualifier, target_id, prompt_text
    return None
