"""Per-type tests: valid/invalid construction and validation behavior
for each of the six concrete knowledge types.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from handbook.models import (
    Algorithm,
    Contest,
    KnowledgeItem,
    Mistake,
    Pattern,
    Problem,
    Topic,
)
from handbook.models.enums import (
    ContestType,
    MistakeCategory,
    PatternCategory,
    Platform,
    ProblemSource,
    RelationType,
)

# -- Algorithm ------------------------------------------------------------


def test_algorithm_minimal_construction():
    algo = Algorithm(title="Binary Lifting")

    assert isinstance(algo, KnowledgeItem)
    assert algo.kind == "algorithm"
    assert algo.pitfalls == []
    assert algo.related_problems == []


def test_algorithm_full_construction():
    algo = Algorithm(
        title="Segment Tree",
        category=PatternCategory.DATA_STRUCTURE,
        time_complexity="O(log n) per query",
        space_complexity="O(n)",
        intuition="Split the array into a binary tree of ranges.",
        pitfalls=["off-by-one in range bounds", "off-by-one in range bounds"],
        related_problems=["Range Sum Query"],
    )

    assert algo.category is PatternCategory.DATA_STRUCTURE
    assert algo.pitfalls == ["off-by-one in range bounds"]  # deduped
    assert algo.related_problems[0].type is RelationType.APPEARS_IN


def test_algorithm_invalid_category_rejected():
    with pytest.raises(ValidationError):
        Algorithm(title="X", category="not-a-category")


# -- Problem ----------------------------------------------------------------


def test_problem_requires_platform_contest_index():
    with pytest.raises(ValidationError):
        Problem(title="X")  # type: ignore[call-arg]


def test_problem_valid_construction():
    problem = Problem(
        title="Two Sum",
        platform="LeetCode",
        contest="Easy",
        index="1",
        rating=1200,
        algorithms=["Hash Map"],
        patterns=["Two Pointers"],
    )

    assert problem.platform is Platform.LEETCODE
    assert problem.source is ProblemSource.PRACTICE
    assert problem.algorithms[0].type is RelationType.USES
    assert problem.solved is True


def test_problem_blank_contest_or_index_rejected():
    with pytest.raises(ValidationError):
        Problem(title="X", platform="CF", contest="  ", index="A")
    with pytest.raises(ValidationError):
        Problem(title="X", platform="CF", contest="A", index="")


def test_problem_rating_must_be_positive():
    with pytest.raises(ValidationError):
        Problem(title="X", platform="CF", contest="A", index="1", rating=0)
    with pytest.raises(ValidationError):
        Problem(title="X", platform="CF", contest="A", index="1", rating=-100)


def test_problem_attempts_cannot_be_negative():
    with pytest.raises(ValidationError):
        Problem(title="X", platform="CF", contest="A", index="1", attempts=-1)


# -- Pattern ------------------------------------------------------------------


def test_pattern_minimal_construction():
    pattern = Pattern(title="Sliding Window")

    assert pattern.kind == "pattern"
    assert pattern.category is None


def test_pattern_recognition_cues_deduped_case_insensitively():
    pattern = Pattern(
        title="Two Pointers",
        recognition_cues=["sorted array", "Sorted Array", "pair sum"],
    )

    assert pattern.recognition_cues == ["sorted array", "pair sum"]


def test_pattern_relation_fields_default_types():
    pattern = Pattern(
        title="Two Pointers",
        related_algorithms=["Binary Search"],
        example_problems=["3Sum"],
    )

    assert pattern.related_algorithms[0].type is RelationType.USES
    assert pattern.example_problems[0].type is RelationType.APPEARS_IN


# -- Mistake ------------------------------------------------------------------


def test_mistake_minimal_construction_defaults():
    mistake = Mistake(title="Off by one")

    assert mistake.category is MistakeCategory.OTHER
    assert mistake.occurrences == 1


def test_mistake_occurrences_must_be_at_least_one():
    with pytest.raises(ValidationError):
        Mistake(title="X", occurrences=0)


def test_mistake_category_alias():
    mistake = Mistake(title="X", category="tle")
    assert mistake.category is MistakeCategory.TIME_LIMIT_EXCEEDED


# -- Contest ------------------------------------------------------------------


def test_contest_requires_platform():
    with pytest.raises(ValidationError):
        Contest(title="X")  # type: ignore[call-arg]


def test_contest_valid_construction():
    contest = Contest(
        title="Educational Round 100",
        platform="cf",
        contest_type="rated",
        problems=["A", "B", "C"],
        rank=1234,
        takeaways=["read constraints twice", "read constraints twice"],
    )

    assert contest.platform is Platform.CODEFORCES
    assert contest.contest_type is ContestType.RATED
    assert len(contest.problems) == 3
    assert contest.problems[0].type is RelationType.CONTAINS
    assert contest.takeaways == ["read constraints twice"]  # deduped


def test_contest_rank_must_be_at_least_one():
    with pytest.raises(ValidationError):
        Contest(title="X", platform="CF", rank=0)


def test_contest_duration_must_be_positive():
    with pytest.raises(ValidationError):
        Contest(title="X", platform="CF", duration_minutes=0)


# -- Topic ----------------------------------------------------------------------


def test_topic_minimal_construction():
    topic = Topic(title="Graph Theory")

    assert topic.kind == "topic"
    assert topic.area is None


def test_topic_children_default_to_contains():
    topic = Topic(
        title="Graph Theory",
        algorithms=["DFS", "BFS"],
        patterns=["Union-Find"],
        key_problems=["Number of Islands"],
    )

    assert all(rel.type is RelationType.CONTAINS for rel in topic.algorithms)
    assert all(rel.type is RelationType.CONTAINS for rel in topic.patterns)
    assert topic.key_problems[0].type is RelationType.APPEARS_IN


def test_topic_reuses_base_status_for_mastery_rather_than_a_new_field():
    topic = Topic(title="DP", status="Mastered")
    assert topic.status.value == "Mastered"
    assert not hasattr(topic, "mastery_level")
