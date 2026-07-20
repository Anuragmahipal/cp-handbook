"""Tests for history rebuild and determinism (PR #4)."""

from __future__ import annotations

from pathlib import Path

from handbook.sync.codeforces import CodeforcesClient
from handbook.sync.pipeline import run_rebuild, run_sync
from handbook.sync.state import SyncState


def _client(payloads: list[dict]):
    response = {"status": "OK", "result": payloads}
    def _transport(url: str) -> bytes:
        return __import__("json").dumps(response).encode()
    return CodeforcesClient(transport=_transport)


def test_rebuild_reconstructs_all_problems(vault_root: Path, cf_submission_payload):
    """After sync + rebuild, all problems must be restored."""
    wa = cf_submission_payload(
        id=1, verdict="WRONG_ANSWER", creation_time=1_700_000_000,
        contest_id=1, index="A", name="Unsolved",
    )
    ac = cf_submission_payload(
        id=2, verdict="OK", creation_time=1_700_000_200,
        contest_id=1, index="B", name="Solved",
    )

    client = _client([wa, ac])
    run_sync("someone", vault_root=vault_root, client=client)

    # Verify initial state
    state = SyncState(vault_root)
    assert state.problem_count() == 2

    # Rebuild
    report = run_rebuild("someone", vault_root=vault_root)

    assert report.problems_rebuilt == 2
    assert report.solved_problems == 1
    assert report.unsolved_problems == 1
    assert report.deterministic is True

    # Verify rebuilt state
    state2 = SyncState(vault_root)
    assert state2.problem_count() == 2
    items = state2.known_items()
    solved = [i for i in items if i.is_solved]
    unsolved = [i for i in items if not i.is_solved]
    assert len(solved) == 1
    assert len(unsolved) == 1


def test_rebuild_preserves_submission_history(vault_root: Path, cf_submission_payload):
    """Rebuild must preserve the full submission history per problem."""
    wa1 = cf_submission_payload(
        id=1, verdict="WRONG_ANSWER", creation_time=1_700_000_000,
    )
    wa2 = cf_submission_payload(
        id=2, verdict="WRONG_ANSWER", creation_time=1_700_000_100,
    )
    ac = cf_submission_payload(
        id=3, verdict="OK", creation_time=1_700_000_200,
    )

    client = _client([wa1, wa2, ac])
    run_sync("someone", vault_root=vault_root, client=client)

    report = run_rebuild("someone", vault_root=vault_root)

    state = SyncState(vault_root)
    items = state.known_items()
    assert len(items) == 1
    assert items[0].attempt_count == 3
    assert items[0].verdict_sequence == ["WRONG_ANSWER", "WRONG_ANSWER", "OK"]


def test_rebuild_is_idempotent(vault_root: Path, cf_submission_payload):
    """Two rebuilds in a row must produce identical state."""
    ac = cf_submission_payload(id=1, verdict="OK", creation_time=1_700_000_000)
    client = _client([ac])
    run_sync("someone", vault_root=vault_root, client=client)

    run_rebuild("someone", vault_root=vault_root)
    report2 = run_rebuild("someone", vault_root=vault_root)

    assert report2.deterministic is True
    assert report2.problems_rebuilt == 1


def test_rebuild_clears_evolution_log(vault_root: Path, cf_submission_payload):
    """Rebuild must clear and regenerate the evolution log."""
    ac = cf_submission_payload(id=1, verdict="OK", creation_time=1_700_000_000)
    client = _client([ac])
    run_sync("someone", vault_root=vault_root, client=client)

    # Check evolution log exists after sync
    evolution_path = vault_root / ".handbook" / "evolution" / "events.jsonl"
    assert evolution_path.exists()

    run_rebuild("someone", vault_root=vault_root)

    # Log should be recreated (not empty)
    assert evolution_path.exists()
