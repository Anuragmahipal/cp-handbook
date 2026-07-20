"""Tests for unsolved problem tracking (PR #3)."""

from __future__ import annotations

from pathlib import Path

from handbook.sync.codeforces import CodeforcesClient
from handbook.sync.pipeline import run_sync
from handbook.sync.state import SyncState


def _client(payloads: list[dict]):
    response = {"status": "OK", "result": payloads}
    def _transport(url: str) -> bytes:
        return __import__("json").dumps(response).encode()
    return CodeforcesClient(transport=_transport)


def test_unsolved_problem_created_with_solved_false(
    vault_root: Path, cf_submission_payload
):
    """A problem with only WA submissions must become an unsolved Problem."""
    wa = cf_submission_payload(id=1, verdict="WRONG_ANSWER", creation_time=1_700_000_000)
    client = _client([wa])

    run_sync("someone", vault_root=vault_root, client=client)

    state = SyncState(vault_root)
    items = state.known_items()
    assert len(items) == 1
    problem = items[0]
    assert problem.is_solved is False
    assert problem.solved_at is None
    assert problem.attempt_count == 1


def test_unsolved_problems_ordered_by_attempts(
    vault_root: Path, cf_submission_payload
):
    """Unsolved problems must be ordered: attempts desc, then rating desc."""
    # Problem A: 1 WA, rating 1200
    wa_a = cf_submission_payload(
        id=1, verdict="WRONG_ANSWER", creation_time=1_700_000_000,
        contest_id=1, index="A", name="Easy", rating=1200,
    )
    # Problem B: 3 WA, rating 1500
    wa_b1 = cf_submission_payload(
        id=2, verdict="WRONG_ANSWER", creation_time=1_700_000_100,
        contest_id=1, index="B", name="Medium", rating=1500,
    )
    wa_b2 = cf_submission_payload(
        id=3, verdict="WRONG_ANSWER", creation_time=1_700_000_200,
        contest_id=1, index="B", name="Medium", rating=1500,
    )
    wa_b3 = cf_submission_payload(
        id=4, verdict="WRONG_ANSWER", creation_time=1_700_000_300,
        contest_id=1, index="B", name="Medium", rating=1500,
    )

    client = _client([wa_a, wa_b1, wa_b2, wa_b3])
    run_sync("someone", vault_root=vault_root, client=client)

    state = SyncState(vault_root)
    items = state.known_items()
    assert len(items) == 2
    b = next(i for i in items if i.title == "Medium")
    a = next(i for i in items if i.title == "Easy")
    assert b.attempt_count == 3
    assert a.attempt_count == 1


def test_mixed_solved_and_unsolved_problems(
    vault_root: Path, cf_submission_payload
):
    """Both solved and unsolved problems must be tracked together."""
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

    state = SyncState(vault_root)
    items = state.known_items()
    assert len(items) == 2
    solved = [i for i in items if i.is_solved]
    unsolved = [i for i in items if not i.is_solved]
    assert len(solved) == 1
    assert len(unsolved) == 1
    assert solved[0].title == "Solved"
    assert unsolved[0].title == "Unsolved"


def test_unsolved_problem_no_revision_note(
    vault_root: Path, cf_submission_payload
):
    """Unsolved problems should not generate revision notes."""
    wa = cf_submission_payload(id=1, verdict="WRONG_ANSWER", creation_time=1_700_000_000)
    client = _client([wa])

    report = run_sync("someone", vault_root=vault_root, client=client)

    # No imported items (which carry revision notes) for unsolved problems
    assert len(report.imported) == 0
    assert report.newly_accepted == 0
