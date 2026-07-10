"""Tests for the lenient str-enum base and its subclasses."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from handbook.models import Algorithm, Platform, Problem
from handbook.models.enums import ContestType, Difficulty, PatternCategory


def test_exact_canonical_value_matches():
    assert Platform("Codeforces") is Platform.CODEFORCES


def test_case_insensitive_match():
    assert Platform("codeforces") is Platform.CODEFORCES
    assert Platform("LEETCODE") is Platform.LEETCODE


def test_known_alias_resolves_to_canonical_member():
    assert Platform("cf") is Platform.CODEFORCES
    assert Platform("CF") is Platform.CODEFORCES
    assert Platform("lc") is Platform.LEETCODE


def test_unrecognized_value_raises():
    with pytest.raises(ValueError):
        Platform("definitely-not-a-platform")


def test_pydantic_field_uses_the_same_lenient_coercion():
    problem = Problem(title="X", platform="cf", contest="1", index="A")

    assert problem.platform is Platform.CODEFORCES


def test_pydantic_field_rejects_unrecognized_value():
    with pytest.raises(ValidationError):
        Problem(title="X", platform="not-a-real-platform", contest="1", index="A")


def test_pattern_category_alias():
    assert PatternCategory("dp") is PatternCategory.DYNAMIC_PROGRAMMING


def test_difficulty_lenient_case():
    algo = Algorithm(title="X", difficulty="hard")
    assert algo.difficulty is Difficulty.HARD


def test_contest_type_default_and_alias():
    assert ContestType("rated") is ContestType.RATED
