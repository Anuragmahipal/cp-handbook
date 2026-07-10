"""The domain base every knowledge type builds on.

``KnowledgeItem`` carries the metadata that is meaningful for *any* CP
knowledge object -- identity, classification, provenance, relationships,
and timestamps -- so every future feature (search, graph, MCP,
recommendations) can be written once against this base instead of
special-cased per knowledge type.

``Relation`` is the first-class relationship primitive: a typed edge to
another item, used for prerequisites, "related items", and every
type-specific relationship field (``Problem.algorithms``,
``Pattern.related_algorithms``, ``Contest.problems``, ...). Modeling
relationships as data (target + type) rather than free-form Markdown
links is what lets a future graph layer walk the knowledge base
directly instead of parsing prose.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from handbook.models.enums import Difficulty, KnowledgeStatus, RelationType
from handbook.utils.slug import note_slug


class Relation(BaseModel):
    """A typed, first-class edge from one knowledge item to another.

    ``target`` is deliberately a plain string (an id, title, or alias)
    rather than a foreign key into a database: the knowledge model layer
    has no query/index of its own yet, so relations describe *intent*
    ("this problem uses Binary Lifting") without requiring the target to
    already exist. Resolving targets to concrete objects is a job for a
    later chunk (Search/Graph), not this one.
    """

    target: str
    type: RelationType = RelationType.RELATED
    note: str = ""
    """Optional short context for why this relationship holds, e.g.
    'needed for the doubling technique'."""

    @field_validator("target", mode="before")
    @classmethod
    def _strip_target(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    @field_validator("target")
    @classmethod
    def _target_not_blank(cls, v: str) -> str:
        if not v:
            raise ValueError("Relation.target must not be blank")
        return v

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"{self.type.value} -> {self.target}"


def coerce_relations(
    value: object, *, default_type: RelationType = RelationType.RELATED
) -> object:
    """``mode="before"`` helper: let relation-list fields accept plain strings.

    ``["Two Sum", "3Sum"]`` becomes a list of two ``Relation`` objects,
    both using ``default_type``.
    ``Relation`` instances and dicts pass through untouched. This means a
    caller (human or AI agent) that doesn't know about ``Relation`` yet
    can still just pass a list of names and get properly typed,
    structured data back -- it's an ergonomic on-ramp, not a second
    source of truth.
    """
    if not isinstance(value, list):
        return value
    return [
        Relation(target=v, type=default_type) if isinstance(v, str) else v
        for v in value
    ]


def _dedupe_normalize(values: list[str], *, lowercase: bool) -> list[str]:
    """Strip whitespace, drop blanks, and remove duplicates, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        cleaned = raw.strip()
        if not cleaned:
            continue
        normalized = cleaned.lower() if lowercase else cleaned
        key = normalized.lower() if not lowercase else normalized
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


class KnowledgeItem(BaseModel):
    """Base class for every knowledge item in the handbook.

    Fields are grouped by purpose (identity / classification / provenance
    / relationships / free text / timestamps) rather than declared in an
    arbitrary order, so subclasses read as "the base, plus what's
    special about this type" rather than a flat bag of attributes.
    """

    KIND: ClassVar[str] = "knowledge_item"
    """Stable, human-readable discriminator for this knowledge type.

    Deliberately independent of the Python class name, so serialized
    data (and any future polymorphic loader that branches on ``kind``)
    stays stable even if classes are renamed or reorganized later.
    Overridden by every concrete subclass.
    """

    # -- identity --------------------------------------------------------
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    aliases: list[str] = Field(default_factory=list)

    # -- classification ---------------------------------------------------
    tags: list[str] = Field(default_factory=list)
    difficulty: Difficulty | None = None
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE

    # -- provenance --------------------------------------------------------
    sources: list[str] = Field(default_factory=list)
    """Where this knowledge came from: an editorial, a book, a video."""
    references: list[str] = Field(default_factory=list)
    """Further reading -- distinct from ``sources``, which is about
    origin rather than elaboration."""

    # -- relationships (first-class, typed; see `Relation`) -----------------
    prerequisites: list[Relation] = Field(default_factory=list)
    related_items: list[Relation] = Field(default_factory=list)

    # -- free text ----------------------------------------------------------
    notes: str = ""

    # -- timestamps -----------------------------------------------------
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slug(self) -> str:
        """Canonical, filesystem-safe identifier derived from ``title``.

        Exposed here (rather than left implicit in the storage layer) so
        anything treating this object as a knowledge node -- search, the
        graph layer, an AI agent -- has one obvious canonical identifier
        to key off, matching the exact slug storage uses for filenames.
        """
        return note_slug(self.title)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def kind(self) -> str:
        """This item's knowledge type, e.g. ``"algorithm"``, ``"problem"``."""
        return self.KIND

    @field_validator("prerequisites", "related_items", mode="before")
    @classmethod
    def _coerce_base_relations(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.PREREQUISITE)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, v: list[str]) -> list[str]:
        return _dedupe_normalize(v, lowercase=True)

    @field_validator("aliases", "sources", "references")
    @classmethod
    def _normalize_string_list(cls, v: list[str]) -> list[str]:
        return _dedupe_normalize(v, lowercase=False)

    @model_validator(mode="after")
    def _aliases_exclude_title(self) -> KnowledgeItem:
        """An alias identical to the title carries no information."""
        title_lower = self.title.strip().lower()
        deduped = [a for a in self.aliases if a.lower() != title_lower]
        if deduped != self.aliases:
            self.aliases = deduped
        return self
