"""Integration tests: ``cp-handbook sync`` now records
:mod:`handbook.evolution` history automatically -- covers Part 6
("running sync twice must never destroy history") and the pipeline-
level slice of Part 7's checklist (duplicate sync, incremental sync).
"""

from __future__ import annotations

import json
from pathlib import Path

from handbook.evolution.log import EvolutionLog
from handbook.sync.codeforces import CodeforcesClient
from handbook.sync.pipeline import run_sync


def _client(payloads: list[dict]) -> CodeforcesClient:
    response = {"status": "OK", "result": payloads}

    def _transport(url: str) -> bytes:
        return json.dumps(response).encode()

    return CodeforcesClient(transport=_transport)


def test_sync_records_a_learning_event_for_a_newly_synced_problem(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1)])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert report.evolution is not None
    assert len(report.evolution.learning_events) == 1
    assert (vault_root / ".handbook" / "evolution" / "events.jsonl").exists()


def test_running_sync_twice_on_the_same_data_does_not_duplicate_history(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1, tags=("binary search",))])

    run_sync("someone", vault_root=vault_root, client=client)
    second_report = run_sync("someone", vault_root=vault_root, client=client)

    assert second_report.evolution.is_empty
    log = EvolutionLog(vault_root)
    assert len(log.events()) >= 1  # history from the first run is intact
    # exactly one "solved" event -- not duplicated
    solved_events = [e for e in log.events() if e.kind.value == "solved"]
    assert len(solved_events) == 1


def test_incremental_sync_appends_new_history_without_touching_old(
    vault_root: Path, cf_submission_payload
):
    client_1 = _client([cf_submission_payload(id=1)])
    run_sync("someone", vault_root=vault_root, client=client_1)
    log_after_first = EvolutionLog(vault_root)
    first_event_ids = {e.id for e in log_after_first.events()}

    client_2 = _client(
        [cf_submission_payload(id=1), cf_submission_payload(id=2, index="B", name="Second")]
    )
    run_sync("someone", vault_root=vault_root, client=client_2)
    log_after_second = EvolutionLog(vault_root)
    second_event_ids = {e.id for e in log_after_second.events()}

    assert first_event_ids.issubset(second_event_ids)
    assert len(second_event_ids) > len(first_event_ids)


def test_dashboard_shows_personal_statistics_once_evolution_has_run(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1)])

    report = run_sync("someone", vault_root=vault_root, client=client)

    dashboard_html = report.notebook_site.dashboard_path.read_text(encoding="utf-8")
    assert "Personal Statistics" in dashboard_html


def test_algorithm_page_gains_evolution_sections_after_sync(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1, tags=("binary search",))])

    report = run_sync("someone", vault_root=vault_root, client=client)

    algo_page = next(p for p in report.notebook_site.pages if p.kind == "algorithm")
    html = algo_page.html_path.read_text(encoding="utf-8")
    assert "Learning Progress" in html
    assert "Learning History" in html
