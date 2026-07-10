"""Tests for KnowledgeItem (the shared base) and Relation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from handbook.models import Algorithm, KnowledgeItem, Relation
from handbook.models.enums import Difficulty, KnowledgeStatus, RelationType


def test_minimal_construction_only_needs_a_title():
    item = KnowledgeItem(title="Something")

    assert item.title == "Something"
    assert item.id  # a uuid was generated
    assert item.tags == []
    assert item.status == KnowledgeStatus.ACTIVE
    assert item.difficulty is None


def test_blank_title_is_rejected():
    with pytest.raises(ValidationError):
        KnowledgeItem(title="   ")


def test_missing_title_is_rejected():
    with pytest.raises(ValidationError):
        KnowledgeItem()  # type: ignore[call-arg]


def test_tags_are_normalized_lowercase_stripped_and_deduped():
    item = KnowledgeItem(title="X", tags=["DP", " dp ", "Greedy", "greedy"])

    assert item.tags == ["dp", "greedy"]


def test_aliases_are_stripped_and_deduped_but_case_preserved():
    item = KnowledgeItem(title="X", aliases=["Foo", " Foo ", "Bar"])

    assert item.aliases == ["Foo", "Bar"]


def test_alias_matching_title_is_dropped():
    item = KnowledgeItem(
        title="Binary Search", aliases=["Binary Search", "Binary Srch"]
    )

    assert item.aliases == ["Binary Srch"]


def test_blank_entries_are_dropped_from_list_fields():
    item = KnowledgeItem(title="X", tags=["", "  ", "real-tag"], sources=["", "book"])

    assert item.tags == ["real-tag"]
    assert item.sources == ["book"]


def test_slug_is_derived_from_title():
    item = KnowledgeItem(title="Binary Exponentiation")

    assert item.slug == "binary-exponentiation"


def test_kind_reflects_the_class():
    assert KnowledgeItem(title="X").kind == "knowledge_item"
    assert Algorithm(title="X").kind == "algorithm"


def test_difficulty_and_status_accept_enum_values():
    item = KnowledgeItem(
        title="X", difficulty=Difficulty.HARD, status=KnowledgeStatus.MASTERED
    )

    assert item.difficulty is Difficulty.HARD
    assert item.status is KnowledgeStatus.MASTERED


def test_invalid_difficulty_is_rejected():
    with pytest.raises(ValidationError):
        KnowledgeItem(title="X", difficulty="not-a-real-difficulty")


def test_prerequisites_accept_plain_strings_as_shorthand():
    item = KnowledgeItem(title="HLD", prerequisites=["LCA", "Binary Lifting"])

    assert item.prerequisites == [
        Relation(target="LCA", type=RelationType.PREREQUISITE),
        Relation(target="Binary Lifting", type=RelationType.PREREQUISITE),
    ]


def test_prerequisites_accept_explicit_relations_with_custom_type():
    item = KnowledgeItem(
        title="HLD",
        prerequisites=[
            Relation(target="LCA", type=RelationType.USES, note="core building block")
        ],
    )

    assert item.prerequisites[0].type is RelationType.USES
    assert item.prerequisites[0].note == "core building block"


def test_relation_target_cannot_be_blank():
    with pytest.raises(ValidationError):
        Relation(target="   ")


def test_relation_target_is_stripped():
    assert Relation(target="  LCA  ").target == "LCA"


def test_inheritance_subclass_gets_all_base_fields_and_validation():
    class Custom(KnowledgeItem):
        extra_field: str = ""

    item = Custom(title="X", tags=["A", "a"])

    assert isinstance(item, KnowledgeItem)
    assert item.tags == ["a"]  # base validator still runs on the subclass
    assert item.extra_field == ""
    assert item.kind == "knowledge_item"  # KIND not overridden by Custom


def test_round_trip_serialization_preserves_information():
    original = KnowledgeItem(
        title="Segment Tree",
        tags=["data-structure"],
        aliases=["Seg Tree"],
        difficulty=Difficulty.MEDIUM,
        prerequisites=["Arrays"],
        notes="Supports range queries and point updates.",
    )

    restored = KnowledgeItem.model_validate(original.model_dump(mode="json"))

    assert restored == original
    # computed fields are recomputed identically, not silently dropped
    assert restored.slug == original.slug
    assert restored.kind == original.kind


def test_json_string_round_trip():
    original = KnowledgeItem(title="Fenwick Tree", tags=["bit"])

    restored = KnowledgeItem.model_validate_json(original.model_dump_json())

    assert restored == original
