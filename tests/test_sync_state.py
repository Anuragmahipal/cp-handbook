"""Tests for handbook.sync.state.SyncState: one vault's sync bookkeeping."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from handbook.models import Problem
from handbook.models.submission import Submission
from handbook.sync.state import SyncState


def _problem(**overrides) -> Problem:
    defaults = dict(
        title="Sample Problem",
        platform="Codeforces",
        contest="1868",
        index="A",
    )
    defaults.update(overrides)
    return Problem(**defaults)


def test_fresh_state_has_nothing_imported(vault_root: Path):
    state = SyncState(vault_root)

    assert state.imported_count() == 0
    assert state.problem_count() == 0
    assert state.has_imported(1) is False
    assert state.has_problem("1868A") is False
    assert state.last_synced_at is None


def test_mark_imported_is_tracked(vault_root: Path):
    state = SyncState(vault_root)

    state.mark_imported(42)

    assert state.has_imported(42) is True
    assert state.has_imported(43) is False
    assert state.imported_count() == 1


def test_store_and_retrieve_submission(vault_root: Path):
    state = SyncState(vault_root)
    sub = Submission(
        id=42,
        problem_key="1868A",
        contest_id=1868,
        creation_time_seconds=1_700_000_000,
        verdict="WRONG_ANSWER",
        programming_language="GNU C++20",
        time_consumed_ms=30,
        memory_consumed_bytes=1000,
        passed_test_count=5,
    )

    state.store_submission(sub)

    retrieved = state.get_submission(42)
    assert retrieved is not None
    assert retrieved.id == 42
    assert retrieved.problem_key == "1868A"
    assert retrieved.verdict == "WRONG_ANSWER"
    assert retrieved.accepted is False


def test_submissions_returned_in_chronological_order(vault_root: Path):
    state = SyncState(vault_root)
    state.store_submission(Submission(
        id=2, problem_key="1868A", contest_id=1868,
        creation_time_seconds=1_700_000_100, verdict="OK",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=500, passed_test_count=10,
    ))
    state.store_submission(Submission(
        id=1, problem_key="1868A", contest_id=1868,
        creation_time_seconds=1_700_000_000, verdict="WRONG_ANSWER",
        programming_language="C++", time_consumed_ms=20,
        memory_consumed_bytes=600, passed_test_count=3,
    ))

    subs = state.all_submissions()
    assert [s.id for s in subs] == [1, 2]
    assert subs[0].verdict == "WRONG_ANSWER"
    assert subs[1].verdict == "OK"


def test_submissions_for_problem_filters_correctly(vault_root: Path):
    state = SyncState(vault_root)
    state.store_submission(Submission(
        id=1, problem_key="1868A", contest_id=1868,
        creation_time_seconds=1_700_000_000, verdict="OK",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=500, passed_test_count=10,
    ))
    state.store_submission(Submission(
        id=2, problem_key="1868B", contest_id=1868,
        creation_time_seconds=1_700_000_100, verdict="OK",
        programming_language="C++", time_consumed_ms=15,
        memory_consumed_bytes=600, passed_test_count=10,
    ))

    assert len(state.submissions_for_problem("1868A")) == 1
    assert len(state.submissions_for_problem("1868B")) == 1
    assert len(state.submissions_for_problem("9999Z")) == 0


def test_remember_problem_is_tracked(vault_root: Path):
    state = SyncState(vault_root)
    problem = _problem()

    state.remember_problem("1868A", problem)

    assert state.has_problem("1868A") is True
    assert state.has_problem("1868B") is False
    assert state.problem_count() == 1


def test_known_items_reconstructs_problems(vault_root: Path):
    state = SyncState(vault_root)
    problem = _problem(title="Reconstructed Problem", rating=1500)

    state.remember_problem("1868A", problem)
    items = state.known_items()

    assert len(items) == 1
    assert isinstance(items[0], Problem)
    assert items[0].title == "Reconstructed Problem"
    assert items[0].rating == 1500
    assert items[0].id == problem.id


def test_known_items_reconstructs_with_submissions(vault_root: Path):
    state = SyncState(vault_root)
    problem = _problem(title="Problem With History")

    state.store_submission(Submission(
        id=1, problem_key="1868A", contest_id=1868,
        creation_time_seconds=1_700_000_000, verdict="WRONG_ANSWER",
        programming_language="C++", time_consumed_ms=20,
        memory_consumed_bytes=600, passed_test_count=3,
    ))
    state.store_submission(Submission(
        id=2, problem_key="1868A", contest_id=1868,
        creation_time_seconds=1_700_000_200, verdict="OK",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=500, passed_test_count=10,
    ))
    state.remember_problem("1868A", problem)

    items = state.known_items()
    assert len(items) == 1
    assert items[0].attempt_count == 2
    assert items[0].is_solved is True
    assert items[0].verdict_sequence == ["WRONG_ANSWER", "OK"]


def test_save_and_reload_round_trips_everything(vault_root: Path):
    state = SyncState(vault_root)
    state.handle = "tourist"
    state.last_synced_at = datetime(2026, 1, 1, 12, 0)
    state.mark_imported(1)
    state.mark_imported(2)
    state.store_submission(Submission(
        id=1, problem_key="1868A", contest_id=1868,
        creation_time_seconds=1_700_000_000, verdict="OK",
        programming_language="C++", time_consumed_ms=10,
        memory_consumed_bytes=500, passed_test_count=10,
    ))
    state.remember_problem("1868A", _problem())
    state.save()

    reloaded = SyncState(vault_root)

    assert reloaded.handle == "tourist"
    assert reloaded.last_synced_at == datetime(2026, 1, 1, 12, 0)
    assert reloaded.has_imported(1)
    assert reloaded.has_imported(2)
    assert reloaded.has_imported(3) is False
    assert reloaded.problem_count() == 1
    assert reloaded.get_submission(1) is not None
    assert reloaded.get_submission(1).verdict == "OK"


def test_state_file_written_under_dot_handbook_sync(vault_root: Path):
    state = SyncState(vault_root)
    state.mark_imported(1)
    state.save()

    expected_path = vault_root / ".handbook" / "sync" / "state.json"
    assert expected_path.exists()


def test_reload_before_any_save_does_not_error(vault_root: Path):
    """vault_root doesn't exist yet at all -- SyncState must tolerate that."""
    state = SyncState(vault_root)

    assert state.problem_count() == 0
