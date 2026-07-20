"""Regression tests for timestamp propagation and historical correctness (PR #2).

Every timestamp in the system must originate from Codeforces API data
(creationTimeSeconds), not from sync time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from handbook.models import Problem, Submission
from handbook.models.enums import Platform
from handbook.sync.codeforces import CodeforcesClient
from handbook.sync.pipeline import run_sync
from handbook.sync.state import SyncState


def _client(payloads: list[dict]):
    response = {"status": "OK", "result": payloads}
    def _transport(url: str) -> bytes:
        return __import__("json").dumps(response).encode()
    return CodeforcesClient(transport=_transport)


def test_problem_created_at_equals_first_attempted_at():
    """created_at must be the first submission time, not sync time."""
    from handbook.sync.mapping import build_submission
    from handbook.sync.codeforces import CFProblem, CFSubmission

    problem = CFProblem(
        contest_id=1, problemset_name=None, index="A",
        name="Test", type="PROGRAMMING", rating=1200, tags=(),
    )
    cf_sub = CFSubmission(
        id=1, contest_id=1,
        creation_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        creation_time_seconds=1_705_314_600,
        relative_time_seconds=600,
        problem=problem, verdict="OK", participant_type="CONTESTANT",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=100, passed_test_count=10,
    )

    from handbook.sync.mapping import build_problem_item
    p = build_problem_item(cf_sub, submission_history=[build_submission(cf_sub)])

    assert p.created_at == datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
    assert p.first_attempted_at == p.created_at


def test_problem_updated_at_equals_solved_at():
    """updated_at must be the AC submission time, not sync time."""
    from handbook.sync.mapping import build_submission, build_problem_item
    from handbook.sync.codeforces import CFProblem, CFSubmission

    problem = CFProblem(
        contest_id=1, problemset_name=None, index="A",
        name="Test", type="PROGRAMMING", rating=1200, tags=(),
    )
    wa = CFSubmission(
        id=1, contest_id=1,
        creation_time=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
        creation_time_seconds=1_705_312_800,
        relative_time_seconds=300,
        problem=problem, verdict="WRONG_ANSWER", participant_type="CONTESTANT",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=100, passed_test_count=3,
    )
    ac = CFSubmission(
        id=2, contest_id=1,
        creation_time=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        creation_time_seconds=1_705_314_600,
        relative_time_seconds=600,
        problem=problem, verdict="OK", participant_type="CONTESTANT",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=100, passed_test_count=10,
    )

    history = [build_submission(wa), build_submission(ac)]
    p = build_problem_item(ac, submission_history=history)

    assert p.solved_at == datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
    assert p.updated_at == p.solved_at


def test_unsolved_problem_updated_at_equals_last_submission():
    """For unsolved problems, updated_at = last submission time."""
    from handbook.sync.mapping import build_submission, build_problem_item
    from handbook.sync.codeforces import CFProblem, CFSubmission

    problem = CFProblem(
        contest_id=1, problemset_name=None, index="A",
        name="Test", type="PROGRAMMING", rating=1200, tags=(),
    )
    wa1 = CFSubmission(
        id=1, contest_id=1,
        creation_time=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
        creation_time_seconds=1_705_312_800,
        relative_time_seconds=300,
        problem=problem, verdict="WRONG_ANSWER", participant_type="CONTESTANT",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=100, passed_test_count=3,
    )
    wa2 = CFSubmission(
        id=2, contest_id=1,
        creation_time=datetime(2024, 1, 15, 10, 45, tzinfo=timezone.utc),
        creation_time_seconds=1_705_315_500,
        relative_time_seconds=900,
        problem=problem, verdict="WRONG_ANSWER", participant_type="CONTESTANT",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=100, passed_test_count=5,
    )

    history = [build_submission(wa1), build_submission(wa2)]
    p = build_problem_item(wa2, submission_history=history)

    assert p.is_solved is False
    assert p.solved_at is None
    assert p.updated_at == datetime(2024, 1, 15, 10, 45, tzinfo=timezone.utc)


def test_duplicate_sync_preserves_historical_timestamps(vault_root: Path, cf_submission_payload):
    """Running sync twice must not change Problem timestamps."""
    payload = cf_submission_payload(
        id=1, creation_time=1_705_314_600, verdict="OK"
    )
    client = _client([payload])

    run_sync("someone", vault_root=vault_root, client=client)

    state = SyncState(vault_root)
    items = state.known_items()
    assert len(items) == 1
    first = items[0]

    # Run sync again
    run_sync("someone", vault_root=vault_root, client=client)

    state2 = SyncState(vault_root)
    items2 = state2.known_items()
    assert len(items2) == 1
    second = items2[0]

    assert first.created_at == second.created_at
    assert first.updated_at == second.updated_at
    assert first.solved_at == second.solved_at


def test_stats_use_solved_at_not_created_at():
    """personal_statistics must count solves by solved_at, not created_at."""
    from handbook.evolution.stats import personal_statistics

    # Create problems with different created_at vs solved_at
    p1 = Problem(
        title="P1", platform=Platform.CODEFORCES, contest="1", index="A",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
        solved_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
        solved=True,
        submissions=[Submission(
            id=1, problem_key="1A", contest_id=1,
            creation_time_seconds=1_704_864_000, verdict="OK",
            programming_language="C++", time_consumed_ms=10,
            memory_consumed_bytes=100, passed_test_count=10,
        )],
    )
    p2 = Problem(
        title="P2", platform=Platform.CODEFORCES, contest="1", index="B",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
        solved_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
        solved=True,
        submissions=[Submission(
            id=2, problem_key="1B", contest_id=1,
            creation_time_seconds=1_704_432_000, verdict="OK",
            programming_language="C++", time_consumed_ms=10,
            memory_consumed_bytes=100, passed_test_count=10,
        )],
    )

    stats = personal_statistics([p1, p2], algorithm_count=0, knowledge_growth_events=0)

    # Both solved, so current_streak should be based on solve dates
    # Latest solve is Jan 10, previous is Jan 5 — gap is 5 days > 1 day tolerance
    # So current streak = 1, longest = 1
    assert stats.current_streak_days == 1
    assert stats.longest_streak_days == 1


def test_streaks_computed_from_solve_dates():
    """Consecutive-day streaks must use solved_at.date()."""
    from handbook.evolution.stats import _solve_streaks

    problems = [
        Problem(
            title=f"P{i}", platform=Platform.CODEFORCES, contest="1", index=str(i),
            solved=True,
            submissions=[Submission(
                id=i, problem_key=f"1{i}", contest_id=1,
                creation_time_seconds=int(datetime(2024, 1, d, tzinfo=timezone.utc).timestamp()),
                verdict="OK", programming_language="C++", time_consumed_ms=10,
                memory_consumed_bytes=100, passed_test_count=10,
            )],
        )
        for i, d in enumerate([1, 2, 3, 5, 6], start=1)
    ]

    current, longest = _solve_streaks(problems)

    # Days: 1,2,3 (streak=3), gap, 5,6 (streak=2)
    assert current == 2  # last streak: 5,6
    assert longest == 3  # longest streak: 1,2,3
