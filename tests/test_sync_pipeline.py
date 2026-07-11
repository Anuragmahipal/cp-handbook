"""Tests for handbook.sync.pipeline.run_sync: the full end-to-end pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from handbook.sync.codeforces import CodeforcesClient
from handbook.sync.pipeline import run_sync
from handbook.sync.state import SyncState


def _client(payloads: list[dict]) -> CodeforcesClient:
    response = {"status": "OK", "result": payloads}

    def _transport(url: str) -> bytes:
        return json.dumps(response).encode()

    return CodeforcesClient(transport=_transport)


def test_sync_imports_a_single_accepted_submission(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1)])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert report.fetched_submissions == 1
    assert report.newly_accepted == 1
    assert len(report.imported) == 1
    assert report.imported[0].item.title == "Sample Problem"
    assert report.imported[0].vault_path.exists()
    assert report.imported[0].note_paths.markdown_path.exists()
    assert report.imported[0].note_paths.json_path.exists()


def test_sync_ignores_non_accepted_submissions(vault_root: Path, cf_submission_payload):
    client = _client([cf_submission_payload(id=1, verdict="WRONG_ANSWER")])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert report.newly_accepted == 0
    assert report.imported == []


def test_sync_is_idempotent_across_repeated_runs(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1)])

    first = run_sync("someone", vault_root=vault_root, client=client)
    second = run_sync("someone", vault_root=vault_root, client=client)

    assert len(first.imported) == 1
    assert len(second.imported) == 0
    assert second.newly_accepted == 0
    assert second.total_known_problems == 1


def test_never_creates_a_second_note_for_a_re_solved_problem(
    vault_root: Path, cf_submission_payload
):
    """Same Codeforces problem, solved (accepted) twice -- e.g. resubmitted
    in a different language. Both submission ids get marked imported, but
    only one Problem note/revision note should ever exist."""
    first_ac = cf_submission_payload(id=1, creation_time=1_700_000_000)
    second_ac = cf_submission_payload(id=2, creation_time=1_700_001_000)
    client = _client([first_ac, second_ac])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert report.newly_accepted == 2
    assert len(report.imported) == 1
    assert report.already_known == 1

    state = SyncState(vault_root)
    assert state.has_imported(1)
    assert state.has_imported(2)
    assert state.problem_count() == 1


def test_prior_wrong_attempts_are_counted_before_the_accepted_submission(
    vault_root: Path, cf_submission_payload
):
    wa = cf_submission_payload(
        id=1, verdict="WRONG_ANSWER", creation_time=1_700_000_000
    )
    tle = cf_submission_payload(
        id=2, verdict="TIME_LIMIT_EXCEEDED", creation_time=1_700_000_100
    )
    ac = cf_submission_payload(id=3, verdict="OK", creation_time=1_700_000_200)
    client = _client([wa, tle, ac])

    report = run_sync("someone", vault_root=vault_root, client=client)

    imported_item = report.imported[0].item
    assert imported_item.attempts == 3  # 2 wrong + the accepted one
    assert "2 failed attempts before AC" in report.imported[0].note.mistake


def test_submissions_after_the_accepted_one_do_not_count_as_prior_mistakes(
    vault_root: Path, cf_submission_payload
):
    ac = cf_submission_payload(id=1, verdict="OK", creation_time=1_700_000_000)
    later_wa = cf_submission_payload(
        id=2, verdict="WRONG_ANSWER", creation_time=1_700_000_500
    )
    client = _client([ac, later_wa])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert report.imported[0].item.attempts == 1


def test_graph_connects_problems_sharing_a_tag(vault_root: Path, cf_submission_payload):
    p1 = cf_submission_payload(
        id=1, contest_id=1, index="A", name="Problem One", tags=("dp",)
    )
    p2 = cf_submission_payload(
        id=2, contest_id=1, index="B", name="Problem Two", tags=("dp", "graphs")
    )
    client = _client([p1, p2])

    report = run_sync("someone", vault_root=vault_root, client=client)

    # 2 Problem nodes + 2 shadow topic nodes (Dynamic Programming, Graph Theory)
    assert report.graph_node_count == 4
    assert report.graph_edge_count == 3


def test_graph_json_is_exported_to_vault(vault_root: Path, cf_submission_payload):
    client = _client([cf_submission_payload(id=1)])

    run_sync("someone", vault_root=vault_root, client=client)

    graph_path = vault_root / ".handbook" / "graph.json"
    assert graph_path.exists()
    data = json.loads(graph_path.read_text())
    assert "nodes" in data and "edges" in data


def test_duplicate_report_flags_same_title_from_two_problems(
    vault_root: Path, cf_submission_payload
):
    p1 = cf_submission_payload(id=1, contest_id=1, index="A", name="Same Title")
    p2 = cf_submission_payload(id=2, contest_id=2, index="A", name="Same Title")
    client = _client([p1, p2])

    report = run_sync("someone", vault_root=vault_root, client=client)

    # Both problems are still stored -- a genuine title collision between
    # two different problems disambiguates rather than crashing the sync,
    # and the disambiguated title is exactly why the graph no longer
    # considers them duplicates of each other.
    assert len(report.imported) == 2
    assert report.imported[0].vault_path != report.imported[1].vault_path
    assert report.imported[0].vault_path.exists()
    assert report.imported[1].vault_path.exists()
    assert report.imported[1].item.title != "Same Title"
    assert "Same Title" in report.imported[1].item.title
    assert report.duplicate_report is not None
    assert report.duplicate_report.duplicate_titles == []


def test_state_persists_handle_and_last_synced_at(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1)])

    run_sync("tourist", vault_root=vault_root, client=client)

    state = SyncState(vault_root)
    assert state.handle == "tourist"
    assert state.last_synced_at is not None


def test_duplicate_report_flags_genuine_near_duplicate_titles(
    vault_root: Path, cf_submission_payload
):
    p1 = cf_submission_payload(
        id=1, contest_id=1, index="A", name="Binary Exponentiation"
    )
    p2 = cf_submission_payload(
        id=2, contest_id=2, index="A", name="Binary Exponentation"
    )
    client = _client([p1, p2])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert len(report.imported) == 2  # distinct titles, no collision handling needed
    assert report.duplicate_report is not None
    assert not report.duplicate_report.is_empty()
    assert len(report.duplicate_report.near_duplicate_names) == 1


def test_gym_problem_without_contest_id_is_handled(
    vault_root: Path, cf_submission_payload
):
    payload = cf_submission_payload(
        id=1, contest_id=None, problemset_name="acmsguru", index="101"
    )
    client = _client([payload])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert len(report.imported) == 1
    assert report.imported[0].item.contest == "acmsguru"


def test_second_sync_rebuilds_graph_over_cumulative_items(
    vault_root: Path, cf_submission_payload
):
    """A second sync run, with one more new problem, should build the
    graph over BOTH the old and new problems -- not just this run's."""
    first_client = _client(
        [cf_submission_payload(id=1, contest_id=1, index="A", name="P1")]
    )
    run_sync("someone", vault_root=vault_root, client=first_client)

    second_client = _client(
        [
            cf_submission_payload(id=1, contest_id=1, index="A", name="P1"),
            cf_submission_payload(id=2, contest_id=1, index="B", name="P2"),
        ]
    )
    report = run_sync("someone", vault_root=vault_root, client=second_client)

    assert report.total_known_problems == 2
    assert report.graph_node_count >= 2  # both P1 and P2 present in the rebuilt graph
