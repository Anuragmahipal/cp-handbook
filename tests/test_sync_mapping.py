"""Tests for handbook.sync.mapping: pure, mechanical CF -> handbook conversions."""

from __future__ import annotations

from datetime import datetime

from handbook.models.enums import Difficulty, Platform, ProblemSource
from handbook.sync.codeforces import CFProblem, CFSubmission
from handbook.sync.mapping import (
    build_problem_item,
    difficulty_from_rating,
    source_from_participant_type,
    time_spent_minutes,
    topic_name_for_tag,
)


def test_difficulty_from_rating_none_is_none():
    assert difficulty_from_rating(None) is None


def test_difficulty_from_rating_buckets():
    assert difficulty_from_rating(800) == Difficulty.TRIVIAL
    assert difficulty_from_rating(1199) == Difficulty.TRIVIAL
    assert difficulty_from_rating(1200) == Difficulty.EASY
    assert difficulty_from_rating(1399) == Difficulty.EASY
    assert difficulty_from_rating(1400) == Difficulty.MEDIUM
    assert difficulty_from_rating(1799) == Difficulty.MEDIUM
    assert difficulty_from_rating(1800) == Difficulty.HARD
    assert difficulty_from_rating(2199) == Difficulty.HARD
    assert difficulty_from_rating(2200) == Difficulty.VERY_HARD
    assert difficulty_from_rating(2699) == Difficulty.VERY_HARD
    assert difficulty_from_rating(2700) == Difficulty.EXPERT
    assert difficulty_from_rating(3500) == Difficulty.EXPERT


def test_source_from_participant_type_known_values():
    assert source_from_participant_type("CONTESTANT") == ProblemSource.CONTEST
    assert source_from_participant_type("PRACTICE") == ProblemSource.PRACTICE
    assert source_from_participant_type("VIRTUAL") == ProblemSource.VIRTUAL_CONTEST
    assert source_from_participant_type("OUT_OF_COMPETITION") == ProblemSource.UPSOLVE
    assert source_from_participant_type("MANAGER") == ProblemSource.OTHER


def test_source_from_participant_type_unknown_or_none_falls_back_to_other():
    assert source_from_participant_type(None) == ProblemSource.OTHER
    assert source_from_participant_type("SOMETHING_NEW") == ProblemSource.OTHER


def test_time_spent_minutes_converts_seconds():
    assert time_spent_minutes(120) == 2
    assert time_spent_minutes(90) == 1


def test_time_spent_minutes_none_for_missing_value():
    assert time_spent_minutes(None) is None


def test_time_spent_minutes_rejects_codeforces_sentinel_value():
    """Codeforces uses 2^31 - 1 for submissions with no real contest clock."""
    assert time_spent_minutes(2**31 - 1) is None


def test_time_spent_minutes_rejects_negative_values():
    assert time_spent_minutes(-5) is None


def test_topic_name_for_known_tag():
    assert topic_name_for_tag("dp") == "Dynamic Programming"
    assert topic_name_for_tag("DP") == "Dynamic Programming"
    assert topic_name_for_tag("  dsu  ") == "Disjoint Set Union"


def test_topic_name_for_unknown_tag_falls_back_to_title_case():
    assert topic_name_for_tag("some-new-tag") == "Some-New-Tag"


# -- build_problem_item ----------------------------------------------------


def _submission(
    *,
    contest_id: int | None = 1868,
    index: str = "A",
    rating: int | None = 1200,
    tags=("dp", "implementation"),
    relative_time_seconds: int | None = 600,
    participant_type: str | None = "CONTESTANT",
    problemset_name: str | None = None,
) -> CFSubmission:
    problem = CFProblem(
        contest_id=contest_id,
        problemset_name=problemset_name,
        index=index,
        name="Test Problem",
        type="PROGRAMMING",
        rating=rating,
        tags=tags,
    )
    return CFSubmission(
        id=1,
        contest_id=contest_id,
        creation_time=datetime.now(),
        relative_time_seconds=relative_time_seconds,
        problem=problem,
        verdict="OK",
        participant_type=participant_type,
        programming_language="GNU C++20",
    )


def test_build_problem_item_maps_every_field():
    submission = _submission()

    item = build_problem_item(submission, prior_wrong_attempts=2)

    assert item.title == "Test Problem"
    assert item.platform == Platform.CODEFORCES
    assert item.contest == "1868"
    assert item.contest_id == "1868"
    assert item.index == "A"
    assert item.url == "https://codeforces.com/contest/1868/problem/A"
    assert item.rating == 1200
    assert item.difficulty == Difficulty.EASY
    assert item.source == ProblemSource.CONTEST
    assert item.tags == ["dp", "implementation"]
    assert {r.target for r in item.algorithms} == {
        "Dynamic Programming",
        "Implementation",
    }
    assert item.solved is True
    assert item.attempts == 3  # 2 prior wrong + this AC
    assert item.time_spent_minutes == 10  # 600 seconds


def test_build_problem_item_without_contest_id_uses_problemset_name():
    submission = _submission(contest_id=None, problemset_name="acmsguru", index="101")

    item = build_problem_item(submission, prior_wrong_attempts=0)

    assert item.contest == "acmsguru"
    assert item.contest_id is None
    assert item.url == ""
    assert item.attempts == 1
    assert item.time_spent_minutes is None  # no contest clock to speak of


def test_build_problem_item_first_try_has_one_attempt():
    submission = _submission()

    item = build_problem_item(submission, prior_wrong_attempts=0)

    assert item.attempts == 1
