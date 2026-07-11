"""Tests for handbook.sync.state.SyncState: one vault's sync bookkeeping."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from handbook.models import Problem
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


def test_save_and_reload_round_trips_everything(vault_root: Path):
    state = SyncState(vault_root)
    state.handle = "tourist"
    state.last_synced_at = datetime(2026, 1, 1, 12, 0)
    state.mark_imported(1)
    state.mark_imported(2)
    state.remember_problem("1868A", _problem())
    state.save()

    reloaded = SyncState(vault_root)

    assert reloaded.handle == "tourist"
    assert reloaded.last_synced_at == datetime(2026, 1, 1, 12, 0)
    assert reloaded.has_imported(1)
    assert reloaded.has_imported(2)
    assert reloaded.has_imported(3) is False
    assert reloaded.problem_count() == 1


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
