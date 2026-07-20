"""Regression tests for submission history and data model (PR #1).

Every submission -- accepted or not -- must be stored as a first-class
historical record. The Problem model must derive its facts (attempts,
solved status, timestamps) from this submission history.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from handbook.models import Problem, Submission
from handbook.models.enums import Platform, ProblemSource
from handbook.sync.codeforces import CFProblem, CFSubmission
from handbook.sync.mapping import build_problem_item, build_submission
from handbook.sync.pipeline import run_sync
from handbook.sync.state import SyncState


def _client(payloads: list[dict]):
    from handbook.sync.codeforces import CodeforcesClient
    response = {"status": "OK", "result": payloads}
    def _transport(url: str) -> bytes:
        return __import__("json").dumps(response).encode()
    return CodeforcesClient(transport=_transport)


# -- Submission model ------------------------------------------------------


def test_submission_accepted_only_for_ok_verdict():
    ok = Submission(id=1, problem_key="A", contest_id=1,
                    creation_time_seconds=1, verdict="OK",
                    programming_language="C++", time_consumed_ms=10,
                    memory_consumed_bytes=100, passed_test_count=10)
    wa = Submission(id=2, problem_key="A", contest_id=1,
                    creation_time_seconds=2, verdict="WRONG_ANSWER",
                    programming_language="C++", time_consumed_ms=10,
                    memory_consumed_bytes=100, passed_test_count=3)

    assert ok.accepted is True
    assert wa.accepted is False


def test_submission_serialization_round_trip():
    original = Submission(
        id=42, problem_key="1868A", contest_id=1868,
        creation_time_seconds=1_700_000_000, verdict="TIME_LIMIT_EXCEEDED",
        programming_language="Python 3", time_consumed_ms=1000,
        memory_consumed_bytes=256000, passed_test_count=5,
    )
    data = original.to_dict()
    restored = Submission.from_dict(data)

    assert restored == original


# -- Problem model with submission history ---------------------------------


def test_problem_derives_attempts_from_submissions():
    problem = Problem(
        title="Test", platform=Platform.CODEFORCES, contest="1", index="A",
        submissions=[
            Submission(id=1, problem_key="1A", contest_id=1,
                       creation_time_seconds=100, verdict="WRONG_ANSWER",
                       programming_language="C++", time_consumed_ms=10,
                       memory_consumed_bytes=100, passed_test_count=3),
            Submission(id=2, problem_key="1A", contest_id=1,
                       creation_time_seconds=200, verdict="OK",
                       programming_language="C++", time_consumed_ms=15,
                       memory_consumed_bytes=100, passed_test_count=10),
        ]
    )

    assert problem.attempt_count == 2
    assert problem.is_solved is True


def test_problem_derives_unsolved_from_no_ac():
    problem = Problem(
        title="Test", platform=Platform.CODEFORCES, contest="1", index="A",
        submissions=[
            Submission(id=1, problem_key="1A", contest_id=1,
                       creation_time_seconds=100, verdict="WRONG_ANSWER",
                       programming_language="C++", time_consumed_ms=10,
                       memory_consumed_bytes=100, passed_test_count=3),
            Submission(id=2, problem_key="1A", contest_id=1,
                       creation_time_seconds=200, verdict="TIME_LIMIT_EXCEEDED",
                       programming_language="C++", time_consumed_ms=10,
                       memory_consumed_bytes=100, passed_test_count=5),
        ]
    )

    assert problem.is_solved is False
    assert problem.solved_at is None
    assert problem.attempt_count == 2


def test_problem_verdict_sequence_is_chronological():
    problem = Problem(
        title="Test", platform=Platform.CODEFORCES, contest="1", index="A",
        submissions=[
            Submission(id=1, problem_key="1A", contest_id=1,
                       creation_time_seconds=300, verdict="OK",
                       programming_language="C++", time_consumed_ms=10,
                       memory_consumed_bytes=100, passed_test_count=10),
            Submission(id=2, problem_key="1A", contest_id=1,
                       creation_time_seconds=100, verdict="WRONG_ANSWER",
                       programming_language="C++", time_consumed_ms=10,
                       memory_consumed_bytes=100, passed_test_count=3),
            Submission(id=3, problem_key="1A", contest_id=1,
                       creation_time_seconds=200, verdict="TIME_LIMIT_EXCEEDED",
                       programming_language="C++", time_consumed_ms=10,
                       memory_consumed_bytes=100, passed_test_count=5),
        ]
    )

    assert problem.verdict_sequence == [
        "WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "OK",
    ]


def test_problem_first_attempted_at_from_earliest_submission():
    problem = Problem(
        title="Test", platform=Platform.CODEFORCES, contest="1", index="A",
        submissions=[
            Submission(id=1, problem_key="1A", contest_id=1,
                       creation_time_seconds=1_700_000_000, verdict="WRONG_ANSWER",
                       programming_language="C++", time_consumed_ms=10,
                       memory_consumed_bytes=100, passed_test_count=3),
        ]
    )

    from datetime import datetime, timezone
    assert problem.first_attempted_at == datetime.fromtimestamp(
        1_700_000_000, tz=timezone.utc
    )


def test_problem_solved_at_from_first_ac():
    problem = Problem(
        title="Test", platform=Platform.CODEFORCES, contest="1", index="A",
        submissions=[
            Submission(id=1, problem_key="1A", contest_id=1,
                       creation_time_seconds=1_700_000_000, verdict="WRONG_ANSWER",
                       programming_language="C++", time_consumed_ms=10,
                       memory_consumed_bytes=100, passed_test_count=3),
            Submission(id=2, problem_key="1A", contest_id=1,
                       creation_time_seconds=1_700_000_200, verdict="OK",
                       programming_language="C++", time_consumed_ms=15,
                       memory_consumed_bytes=100, passed_test_count=10),
        ]
    )

    from datetime import datetime, timezone
    assert problem.solved_at == datetime.fromtimestamp(
        1_700_000_200, tz=timezone.utc
    )


def test_problem_backward_compat_without_submissions():
    """Problems created before PR #1 (no submissions field) still work."""
    problem = Problem(
        title="Legacy", platform=Platform.CODEFORCES, contest="1", index="A",
        solved=True, attempts=3,
    )

    assert problem.is_solved is True
    assert problem.attempt_count == 3


# -- build_problem_item with submission history -----------------------------


def test_build_problem_item_with_wa_to_ac_sequence():
    """The classic WA -> WA -> TLE -> AC sequence must be preserved."""
    problem = CFProblem(
        contest_id=1, problemset_name=None, index="A",
        name="Test", type="PROGRAMMING", rating=1200, tags=("dp",),
    )
    wa1 = CFSubmission(
        id=1, contest_id=1, creation_time=__import__("datetime").datetime.now(),
        creation_time_seconds=100, relative_time_seconds=300,
        problem=problem, verdict="WRONG_ANSWER", participant_type="CONTESTANT",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=100, passed_test_count=3,
    )
    wa2 = CFSubmission(
        id=2, contest_id=1, creation_time=__import__("datetime").datetime.now(),
        creation_time_seconds=200, relative_time_seconds=400,
        problem=problem, verdict="WRONG_ANSWER", participant_type="CONTESTANT",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=100, passed_test_count=3,
    )
    tle = CFSubmission(
        id=3, contest_id=1, creation_time=__import__("datetime").datetime.now(),
        creation_time_seconds=300, relative_time_seconds=500,
        problem=problem, verdict="TIME_LIMIT_EXCEEDED", participant_type="CONTESTANT",
        programming_language="C++", time_consumed_ms=1000,
        memory_consumed_bytes=100, passed_test_count=7,
    )
    ac = CFSubmission(
        id=4, contest_id=1, creation_time=__import__("datetime").datetime.now(),
        creation_time_seconds=400, relative_time_seconds=600,
        problem=problem, verdict="OK", participant_type="CONTESTANT",
        programming_language="C++", time_consumed_ms=15,
        memory_consumed_bytes=100, passed_test_count=10,
    )

    history = [build_submission(s) for s in [wa1, wa2, tle, ac]]
    item = build_problem_item(ac, submission_history=history)

    assert item.attempt_count == 4
    assert item.is_solved is True
    assert item.verdict_sequence == [
        "WRONG_ANSWER", "WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "OK",
    ]


# -- Sync pipeline: all submissions stored ---------------------------------


def test_sync_stores_all_verdict_types(vault_root: Path, cf_submission_payload):
    """Every Codeforces verdict must be stored, not just OK."""
    submissions = [
        cf_submission_payload(id=1, verdict="WRONG_ANSWER", creation_time=1_700_000_000),
        cf_submission_payload(id=2, verdict="TIME_LIMIT_EXCEEDED", creation_time=1_700_000_100),
        cf_submission_payload(id=3, verdict="MEMORY_LIMIT_EXCEEDED", creation_time=1_700_000_200),
        cf_submission_payload(id=4, verdict="RUNTIME_ERROR", creation_time=1_700_000_300),
        cf_submission_payload(id=5, verdict="COMPILATION_ERROR", creation_time=1_700_000_400),
        cf_submission_payload(id=6, verdict="PRESENTATION_ERROR", creation_time=1_700_000_500),
        cf_submission_payload(id=7, verdict="SKIPPED", creation_time=1_700_000_600),
        cf_submission_payload(id=8, verdict="OK", creation_time=1_700_000_700),
    ]
    client = _client(submissions)

    run_sync("someone", vault_root=vault_root, client=client)

    state = SyncState(vault_root)
    assert state.imported_count() == 8
    all_subs = state.all_submissions()
    verdicts = {s.verdict for s in all_subs}
    assert verdicts == {
        "WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "MEMORY_LIMIT_EXCEEDED",
        "RUNTIME_ERROR", "COMPILATION_ERROR", "PRESENTATION_ERROR",
        "SKIPPED", "OK",
    }


def test_duplicate_sync_is_idempotent_for_submissions(
    vault_root: Path, cf_submission_payload
):
    """Running sync twice with the same submissions must not create duplicates."""
    submissions = [
        cf_submission_payload(id=1, verdict="WRONG_ANSWER", creation_time=1_700_000_000),
        cf_submission_payload(id=2, verdict="OK", creation_time=1_700_000_200),
    ]
    client = _client(submissions)

    run_sync("someone", vault_root=vault_root, client=client)
    run_sync("someone", vault_root=vault_root, client=client)

    state = SyncState(vault_root)
    assert state.imported_count() == 2
    assert len(state.all_submissions()) == 2
