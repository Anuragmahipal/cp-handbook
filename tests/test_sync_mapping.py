"""Tests for handbook.sync.mapping: pure, mechanical CF -> handbook conversions."""

from __future__ import annotations

from datetime import datetime

from handbook.models import Submission
from handbook.models.enums import Difficulty, Platform, ProblemSource
from handbook.sync.codeforces import CFProblem, CFSubmission
from handbook.sync.mapping import (
    build_problem_item,
    build_submission,
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


# -- build_submission ----------------------------------------------------


def test_build_submission_maps_all_fields():
    problem = CFProblem(
        contest_id=1868,
        problemset_name=None,
        index="A",
        name="Test Problem",
        type="PROGRAMMING",
        rating=1200,
        tags=("dp",),
    )
    cf_sub = CFSubmission(
        id=42,
        contest_id=1868,
        creation_time=datetime.now(),
        creation_time_seconds=1_700_000_000,
        relative_time_seconds=600,
        problem=problem,
        verdict="OK",
        participant_type="CONTESTANT",
        programming_language="GNU C++20",
        time_consumed_ms=30,
        memory_consumed_bytes=1000,
        passed_test_count=10,
    )

    sub = build_submission(cf_sub)

    assert sub.id == 42
    assert sub.problem_key == "1868A"
    assert sub.contest_id == 1868
    assert sub.creation_time_seconds == 1_700_000_000
    assert sub.verdict == "OK"
    assert sub.programming_language == "GNU C++20"
    assert sub.time_consumed_ms == 30
    assert sub.memory_consumed_bytes == 1000
    assert sub.passed_test_count == 10
    assert sub.accepted is True


def test_build_submission_preserves_wrong_answer_verdict():
    problem = CFProblem(
        contest_id=1868,
        problemset_name=None,
        index="A",
        name="Test Problem",
        type="PROGRAMMING",
        rating=1200,
        tags=(),
    )
    cf_sub = CFSubmission(
        id=1,
        contest_id=1868,
        creation_time=datetime.now(),
        creation_time_seconds=1_700_000_000,
        relative_time_seconds=300,
        problem=problem,
        verdict="WRONG_ANSWER",
        participant_type="CONTESTANT",
        programming_language="Python 3",
        time_consumed_ms=15,
        memory_consumed_bytes=500,
        passed_test_count=3,
    )

    sub = build_submission(cf_sub)

    assert sub.verdict == "WRONG_ANSWER"
    assert sub.accepted is False


# -- build_problem_item ----------------------------------------------------


def _cf_submission(
    *,
    contest_id: int | None = 1868,
    index: str = "A",
    rating: int | None = 1200,
    tags=("dp", "implementation"),
    relative_time_seconds: int | None = 600,
    participant_type: str | None = "CONTESTANT",
    problemset_name: str | None = None,
    verdict: str = "OK",
    creation_time_seconds: int = 1_700_000_000,
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
        creation_time=datetime.fromtimestamp(creation_time_seconds),
        creation_time_seconds=creation_time_seconds,
        relative_time_seconds=relative_time_seconds,
        problem=problem,
        verdict=verdict,
        participant_type=participant_type,
        programming_language="GNU C++20",
        time_consumed_ms=30,
        memory_consumed_bytes=1000,
        passed_test_count=10,
    )


def test_build_problem_item_maps_every_field():
    cf_sub = _cf_submission()
    history = [build_submission(cf_sub)]

    item = build_problem_item(cf_sub, submission_history=history)

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
    assert item.is_solved is True
    assert item.attempt_count == 1
    assert item.time_spent_minutes == 10


def test_build_problem_item_without_contest_id_uses_problemset_name():
    cf_sub = _cf_submission(contest_id=None, problemset_name="acmsguru")
    history = [build_submission(cf_sub)]

    item = build_problem_item(cf_sub, submission_history=history)

    assert item.contest == "acmsguru"
    assert item.contest_id is None
    assert item.url == ""


def test_build_problem_item_first_try_has_one_attempt():
    cf_sub = _cf_submission()
    history = [build_submission(cf_sub)]

    item = build_problem_item(cf_sub, submission_history=history)

    assert item.attempt_count == 1
    assert item.is_solved is True


def test_build_problem_item_counts_multiple_attempts():
    """A problem with WA -> WA -> TLE -> AC should have 4 attempts."""
    wa1 = _cf_submission(verdict="WRONG_ANSWER", creation_time_seconds=1_700_000_000)
    wa2 = _cf_submission(verdict="WRONG_ANSWER", creation_time_seconds=1_700_000_100)
    tle = _cf_submission(
        verdict="TIME_LIMIT_EXCEEDED", creation_time_seconds=1_700_000_200
    )
    ac = _cf_submission(verdict="OK", creation_time_seconds=1_700_000_300)

    history = [
        build_submission(wa1),
        build_submission(wa2),
        build_submission(tle),
        build_submission(ac),
    ]

    item = build_problem_item(ac, submission_history=history)

    assert item.attempt_count == 4
    assert item.is_solved is True
    assert item.verdict_sequence == [
        "WRONG_ANSWER",
        "WRONG_ANSWER",
        "TIME_LIMIT_EXCEEDED",
        "OK",
    ]


def test_build_problem_item_unsolved_has_zero_solved_at():
    """A problem with only WA submissions should be unsolved."""
    wa = _cf_submission(verdict="WRONG_ANSWER")
    history = [build_submission(wa)]

    item = build_problem_item(wa, submission_history=history)

    assert item.is_solved is False
    assert item.solved_at is None
    assert item.attempt_count == 1
