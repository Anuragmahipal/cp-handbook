"""MaterializationEngine: turns bare string references on Problems into
first-class, persisted KnowledgeItems.

The problem
-----------
``Problem.algorithms``, ``.patterns`` and ``.mistakes`` are lists of
:class:`~handbook.models.base.Relation`. Their ``target`` is just a
string -- "Binary Search", "Off By One" -- resolved *at graph-build
time* by :class:`~handbook.graph.resolver.Resolver`. If no persisted
``Algorithm``/``Pattern``/``Mistake`` note exists with that slug, the
resolver doesn't fail; it fabricates a *shadow node* (see
``docs/ARCHITECTURE_NOTES_GRAPH.md``) -- a placeholder graph node that
lets edges resolve cleanly, but that is graph-only. Nothing gets
compiled or rendered for it, because nothing was ever persisted for it.
Today, per ``docs/DEVELOPER_NOTES_SYNC.md``, sync only ever produces
``Problem`` items -- so in practice, in a freshly-synced vault, every
Algorithm/Pattern/Mistake a person's problems reference is a shadow.
They have no page, no aggregated "solved problems", nowhere to write
down the intuition. This module is what gives them one.

What this deliberately does *not* do
-------------------------------------
It does not invent content. A materialized item's free-text fields
(``intuition``, ``implementation``, ``pitfalls``, ``cause``,
``prevention``, ``description``, ...) are left blank. ``notes`` carries
one honest, mechanical sentence recording provenance -- how many
problems referenced it, when -- not invented domain knowledge.
``docs/ARCHITECTURE_NOTES_COMPILER.md`` already drew this line for the
compiler ("a sparse KnowledgeItem compiles to a correspondingly sparse
Page -- never padded, never guessed"); this module draws it in the
same place, one layer up, for exactly the reason
``docs/DEVELOPER_NOTES_SYNC.md`` gave for not doing this automatically
before: "creating real Algorithm notes automatically from tag names
would be guessing at content this prototype has no business guessing
at." The guessing is still out of bounds. What changed is that a
*structural home* -- title, kind, stable id, and real backlinks to
every problem that used it -- is not a guess. It is a fact already
sitting in the vault's own Problems, just not yet given a page of its
own.

Create-once, forever
---------------------
A slug is materialized at most once per vault, ever. Once
``MaterializeState`` has a record of it, this engine will never
re-render or re-store its file again -- on purpose. There is no vault
loader, so this engine cannot tell a freshly-materialized stub apart
from one a person has since filled in with real intuition and pitfalls.
Re-rendering from this engine's own (necessarily blank) copy of the
item would silently overwrite that hand-written prose. Rather than
build a fragile field-by-field merge, this module takes the same
tradeoff ``docs/DEVELOPER_NOTES_SYNC.md`` already accepts for
hand-edited Problem notes -- "invisible until a real vault loader
exists" -- and applies it uniformly here. A materialized item's
*backlinks* (which problems use it) stay fresh on every run regardless,
because those are computed live from the graph at compile time (see
``handbook.learning.compiler.helpers.related_pairs``), not stored on
the item itself.

Stable ids
----------
A materialized item's id is ``uuid5(NAMESPACE, "{kind}:{slug}")`` --
deterministic, not random -- for the same reason
``handbook.learning.compiler.helpers.stable_id`` derives ids
deterministically one layer up: materializing the same slug twice
(from two separate runs, or two engines pointed at the same vault)
must converge on one id, never collide.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID, uuid5

from handbook.exceptions import DuplicateItemError
from handbook.handbook import Handbook
from handbook.materialize.state import MaterializeState
from handbook.models import Algorithm, Contest, Mistake, Pattern, Problem
from handbook.models.base import KnowledgeItem, Relation
from handbook.models.enums import RelationType
from handbook.utils.slug import note_slug

_ID_NAMESPACE = UUID("c9e9a0a0-6b1a-4b8e-9c9b-5a6b7c8d9e0f")

_FIELD_KIND: dict[str, type[KnowledgeItem]] = {
    "algorithms": Algorithm,
    "patterns": Pattern,
    "mistakes": Mistake,
}
_FIELD_PRIORITY: tuple[str, ...] = ("algorithms", "patterns", "mistakes")


def _materialized_id(kind: str, slug: str) -> str:
    return str(uuid5(_ID_NAMESPACE, f"{kind}:{slug}"))


def _provenance_note(reference_count: int) -> str:
    plural = "problem" if reference_count == 1 else "problems"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        f"Auto-materialized by the Materialization Engine on {today}, from "
        f"{reference_count} referencing {plural}. This shell only carries "
        "what was mechanically true at creation time -- add the real "
        "intuition, implementation notes, and pitfalls by hand."
    )


def _pick_field(counts: Counter) -> tuple[str, bool]:
    """Which field "wins" when a slug was referenced under more than one
    (e.g. tagged as an algorithm on one problem, a pattern on another).
    Highest reference count wins; ties break by ``_FIELD_PRIORITY``.
    Returns ``(field_name, was_ambiguous)``.
    """
    ranked = sorted(
        _FIELD_PRIORITY,
        key=lambda name: (-counts.get(name, 0), _FIELD_PRIORITY.index(name)),
    )
    winner = next(name for name in ranked if counts.get(name, 0) > 0)
    ambiguous = sum(1 for name in counts if counts[name] > 0) > 1
    return winner, ambiguous


@dataclass(frozen=True, slots=True)
class MaterializedItem:
    """One item the engine knows about after a :meth:`MaterializationEngine.materialize`
    call -- either freshly created this run, or already known from a
    previous one."""

    item: KnowledgeItem
    is_new: bool
    source_field: str
    reference_count: int


@dataclass(frozen=True, slots=True)
class MaterializationReport:
    created: list[MaterializedItem] = field(default_factory=list)
    already_known: list[MaterializedItem] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def all_items(self) -> list[KnowledgeItem]:
        """Every item -- new or previously known -- that should be fed into
        this run's graph and notebook site alongside the vault's Problems."""
        return [m.item for m in self.created] + [m.item for m in self.already_known]

    def is_empty(self) -> bool:
        return not self.created and not self.already_known


class MaterializationEngine:
    """Scans a vault's ``Problem`` items and materializes the
    Algorithms, Patterns, Mistakes, and Contests they reference into
    real, persisted, first-class ``KnowledgeItem`` notes.
    """

    def __init__(self, handbook: Handbook, state: MaterializeState) -> None:
        self._handbook = handbook
        self._state = state

    def materialize(self, problems: Sequence[Problem]) -> MaterializationReport:
        created: list[MaterializedItem] = []
        already_known: list[MaterializedItem] = []
        skipped: list[str] = []
        warnings: list[str] = []

        for bucket in (
            self._materialize_knowledge_items(problems),
            self._materialize_contests(problems),
        ):
            created.extend(bucket.created)
            already_known.extend(bucket.already_known)
            skipped.extend(bucket.skipped)
            warnings.extend(bucket.warnings)

        return MaterializationReport(
            created=created,
            already_known=already_known,
            skipped=skipped,
            warnings=warnings,
        )

    # -- Algorithm / Pattern / Mistake, from Problem.{algorithms,patterns,mistakes} --

    def _materialize_knowledge_items(
        self, problems: Sequence[Problem]
    ) -> MaterializationReport:
        tallies: dict[str, dict] = {}
        for problem in problems:
            for field_name in _FIELD_KIND:
                for relation in getattr(problem, field_name):
                    title = relation.target.strip()
                    if not title:
                        continue
                    slug = note_slug(title)
                    if not slug:
                        continue
                    bucket = tallies.setdefault(
                        slug, {"title": title, "counts": Counter()}
                    )
                    bucket["counts"][field_name] += 1
                    # Prefer the first-seen literal casing as the canonical
                    # title -- "Binary Search" over a later "binary search".
                    if len(title) and bucket["title"] != title:
                        bucket.setdefault("alt_titles", set()).add(title)

        created: list[MaterializedItem] = []
        already_known: list[MaterializedItem] = []
        skipped: list[str] = []
        warnings: list[str] = []

        for slug, info in sorted(tallies.items()):
            field_name, ambiguous = _pick_field(info["counts"])
            kind_cls = _FIELD_KIND[field_name]
            reference_count = sum(info["counts"].values())

            if ambiguous:
                referenced_as = ", ".join(
                    name for name in _FIELD_PRIORITY if info["counts"].get(name)
                )
                warnings.append(
                    f"{info['title']!r} was referenced as more than one kind "
                    f"({referenced_as}) across different problems; "
                    f"materialized as {kind_cls.KIND} (most-referenced kind wins)."
                )

            existing = self._state.get(slug)
            if existing is not None:
                already_known.append(
                    MaterializedItem(
                        item=existing,
                        is_new=False,
                        source_field=field_name,
                        reference_count=reference_count,
                    )
                )
                continue

            item = kind_cls(
                id=_materialized_id(kind_cls.KIND, slug),
                title=info["title"],
                notes=_provenance_note(reference_count),
            )
            if self._store(item, warnings):
                self._state.remember(slug, item)
                created.append(
                    MaterializedItem(
                        item=item,
                        is_new=True,
                        source_field=field_name,
                        reference_count=reference_count,
                    )
                )
            else:
                skipped.append(info["title"])

        return MaterializationReport(
            created=created, already_known=already_known, skipped=skipped, warnings=warnings
        )

    # -- Contest, from Problem.contest_id / Problem.contest --

    def _materialize_contests(
        self, problems: Sequence[Problem]
    ) -> MaterializationReport:
        groups: dict[str, dict] = {}
        for problem in problems:
            key = (problem.contest_id or problem.contest or "").strip()
            if not key:
                continue
            slug = note_slug(key)
            if not slug:
                continue
            bucket = groups.setdefault(
                slug, {"title": key, "platform": problem.platform, "problem_ids": []}
            )
            bucket["problem_ids"].append(problem.id)

        created: list[MaterializedItem] = []
        already_known: list[MaterializedItem] = []
        skipped: list[str] = []
        warnings: list[str] = []

        for slug, info in sorted(groups.items()):
            existing = self._state.get(slug)
            if existing is not None:
                already_known.append(
                    MaterializedItem(
                        item=existing,
                        is_new=False,
                        source_field="contest",
                        reference_count=len(info["problem_ids"]),
                    )
                )
                continue

            item = Contest(
                id=_materialized_id(Contest.KIND, slug),
                title=info["title"],
                platform=info["platform"],
                problems=[
                    Relation(target=problem_id, type=RelationType.CONTAINS)
                    for problem_id in info["problem_ids"]
                ],
                notes=_provenance_note(len(info["problem_ids"])),
            )
            if self._store(item, warnings):
                self._state.remember(slug, item)
                created.append(
                    MaterializedItem(
                        item=item,
                        is_new=True,
                        source_field="contest",
                        reference_count=len(info["problem_ids"]),
                    )
                )
            else:
                skipped.append(info["title"])

        return MaterializationReport(
            created=created, already_known=already_known, skipped=skipped, warnings=warnings
        )

    def _store(self, item: KnowledgeItem, warnings: list[str]) -> bool:
        """Persist a freshly-materialized item. Returns ``False`` (and
        records a warning instead of raising) if a *different*,
        presumably hand-authored, note already occupies that slug's
        path -- materialization must never clobber a person's own note.
        """
        try:
            self._handbook.store(item)
        except DuplicateItemError:
            warnings.append(
                f"skipped materializing {item.title!r}: a note already exists "
                "at that slug with different content. Leaving it untouched."
            )
            return False
        return True
