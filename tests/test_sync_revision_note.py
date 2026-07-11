"""Tests for handbook.sync.revision_note: the intermediate revision format."""

from __future__ import annotations

from datetime import datetime

from handbook.sync.codeforces import CFProblem, CFSubmission
from handbook.sync.mapping import build_problem_item
from handbook.sync.revision_note import generate_revision_note


def _submission(
    *, id: int, verdict: str | None, creation_time: datetime
) -> CFSubmission:
    problem = CFProblem(
        contest_id=1868,
        problemset_name=None,
        index="A",
        name="Test Problem",
        type="PROGRAMMING",
        rating=1200,
        tags=("dp", "implementation"),
    )
    return CFSubmission(
        id=id,
        contest_id=1868,
        creation_time=creation_time,
        relative_time_seconds=600,
        problem=problem,
        verdict=verdict,
        participant_type="CONTESTANT",
        programming_language="GNU C++20",
    )


def test_note_carries_problem_metadata_forward():
    accepted = _submission(
        id=3, verdict="OK", creation_time=datetime(2026, 1, 1, 12, 0)
    )
    item = build_problem_item(accepted, prior_wrong_attempts=0)

    note = generate_revision_note(item, accepted, [])

    assert note.problem_id == item.id
    assert note.problem_title == "Test Problem"
    assert note.platform == "Codeforces"
    assert note.contest == "1868"
    assert note.index == "A"
    assert note.url == "https://codeforces.com/contest/1868/problem/A"
    assert note.rating == 1200
    assert note.tags == ["dp", "implementation"]
    assert note.solved_at == accepted.creation_time


def test_recognition_includes_tags_and_rating():
    accepted = _submission(id=1, verdict="OK", creation_time=datetime(2026, 1, 1))
    item = build_problem_item(accepted, prior_wrong_attempts=0)

    note = generate_revision_note(item, accepted, [])

    assert "dp" in note.recognition
    assert "implementation" in note.recognition
    assert "1200" in note.recognition


def test_mistake_text_when_solved_first_try():
    accepted = _submission(id=1, verdict="OK", creation_time=datetime(2026, 1, 1))
    item = build_problem_item(accepted, prior_wrong_attempts=0)

    note = generate_revision_note(item, accepted, [])

    assert note.mistake == "Solved on the first attempt."


def test_mistake_text_summarizes_prior_verdicts():
    wa = _submission(
        id=1, verdict="WRONG_ANSWER", creation_time=datetime(2026, 1, 1, 10, 0)
    )
    tle = _submission(
        id=2, verdict="TIME_LIMIT_EXCEEDED", creation_time=datetime(2026, 1, 1, 10, 5)
    )
    accepted = _submission(
        id=3, verdict="OK", creation_time=datetime(2026, 1, 1, 10, 10)
    )
    item = build_problem_item(accepted, prior_wrong_attempts=2)

    note = generate_revision_note(item, accepted, [wa, tle])

    assert "2 failed attempts before AC" in note.mistake
    assert "1x WRONG_ANSWER" in note.mistake
    assert "1x TIME_LIMIT_EXCEEDED" in note.mistake


def test_mistake_text_singular_for_one_prior_attempt():
    wa = _submission(
        id=1, verdict="WRONG_ANSWER", creation_time=datetime(2026, 1, 1, 10, 0)
    )
    accepted = _submission(
        id=2, verdict="OK", creation_time=datetime(2026, 1, 1, 10, 5)
    )
    item = build_problem_item(accepted, prior_wrong_attempts=1)

    note = generate_revision_note(item, accepted, [wa])

    assert "1 failed attempt before AC" in note.mistake


def test_hand_fill_sections_start_blank():
    accepted = _submission(id=1, verdict="OK", creation_time=datetime(2026, 1, 1))
    item = build_problem_item(accepted, prior_wrong_attempts=0)

    note = generate_revision_note(item, accepted, [])

    assert note.core_idea == ""
    assert note.complexity == ""
    assert note.key_observation == ""
    assert note.implementation_trick == ""
