"""Integration tests: ``cp-handbook sync`` automatically compiles and
renders notebook pages -- the "Definition of Done" from the chunk
brief: ``cp-handbook init`` then ``cp-handbook sync`` should be the
only two commands a fresh user ever needs to run.
"""

from __future__ import annotations

import json
from pathlib import Path

from handbook.sync.cli import main
from handbook.sync.codeforces import CodeforcesClient
from handbook.sync.pipeline import run_sync


def _client(payloads: list[dict]) -> CodeforcesClient:
    response = {"status": "OK", "result": payloads}

    def _transport(url: str) -> bytes:
        return json.dumps(response).encode()

    return CodeforcesClient(transport=_transport)


# -- pipeline-level ---------------------------------------------------------


def test_sync_compiles_a_notebook_page_for_the_imported_problem(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1)])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert len(report.notebook_pages) == 1
    page = report.notebook_pages[0]
    assert page.kind == "problem"
    assert page.html_path == vault_root / "Notebook" / "Problems" / "sample-problem.html"
    assert page.html_path.exists()

    html = page.html_path.read_text(encoding="utf-8")
    assert "<html" in html
    assert "Sample Problem" in html


def test_notebook_output_is_a_sibling_of_the_markdown_note_folder(
    vault_root: Path, cf_submission_payload
):
    """Markdown notes and compiled notebook pages are two different
    artifacts of the same knowledge -- never mixed into one folder."""
    client = _client([cf_submission_payload(id=1)])
    run_sync("someone", vault_root=vault_root, client=client)

    assert (vault_root / "Problems" / "sample-problem.md").exists()
    assert (vault_root / "Notebook" / "Problems" / "sample-problem.html").exists()


def test_no_manual_step_required_between_import_and_notebook_page(
    vault_root: Path, cf_submission_payload
):
    """A single `run_sync` call is the only step -- no second command,
    matching the brief's Definition of Done."""
    client = _client([cf_submission_payload(id=1)])
    report = run_sync("someone", vault_root=vault_root, client=client)

    assert len(report.imported) == 1
    assert len(report.notebook_pages) == 1


def test_re_syncing_recompiles_every_known_problem_deterministically(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1)])

    first = run_sync("someone", vault_root=vault_root, client=client)
    second = run_sync("someone", vault_root=vault_root, client=client)

    assert len(first.notebook_pages) == 1
    assert len(second.notebook_pages) == 1  # recompiled, not skipped
    assert (
        first.notebook_pages[0].html_path.read_text()
        == second.notebook_pages[0].html_path.read_text()
    )


def test_multiple_synced_problems_each_get_their_own_notebook_page(
    vault_root: Path, cf_submission_payload
):
    client = _client(
        [
            cf_submission_payload(id=1, contest_id=1868, index="A", name="First Problem"),
            cf_submission_payload(id=2, contest_id=1868, index="B", name="Second Problem"),
        ]
    )
    report = run_sync("someone", vault_root=vault_root, client=client)

    assert len(report.notebook_pages) == 2
    titles = {p.title for p in report.notebook_pages}
    assert titles == {"First Problem", "Second Problem"}
    assert (vault_root / "Notebook" / "Problems" / "first-problem.html").exists()
    assert (vault_root / "Notebook" / "Problems" / "second-problem.html").exists()


def test_notebook_pages_carry_compiler_warnings_for_sparse_content(
    vault_root: Path, cf_submission_payload
):
    """Sync-imported problems are necessarily sparse (no solution notes
    yet) -- that's expected, surfaced as warnings, and never fatal."""
    client = _client([cf_submission_payload(id=1)])
    report = run_sync("someone", vault_root=vault_root, client=client)

    assert report.notebook_pages[0].warnings  # something is always incomplete at import time


# -- CLI-level ---------------------------------------------------------------


def test_cli_sync_reports_compiled_notebook_pages(tmp_path: Path, cf_submission_payload):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "vault"
    main(
        ["init", "--handle", "tourist", "--vault", str(vault_path)],
        config_path=config_path,
    )
    client = _client([cf_submission_payload(id=1)])

    exit_code = main(["sync"], config_path=config_path, client=client)

    assert exit_code == 0
    assert (vault_path / "Notebook" / "Problems" / "sample-problem.html").exists()


def test_cli_sync_twice_still_has_exactly_one_notebook_page(
    tmp_path: Path, cf_submission_payload
):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "vault"
    main(
        ["init", "--handle", "tourist", "--vault", str(vault_path)],
        config_path=config_path,
    )
    client = _client([cf_submission_payload(id=1)])

    main(["sync"], config_path=config_path, client=client)
    main(["sync"], config_path=config_path, client=client)

    notebook_files = list((vault_path / "Notebook" / "Problems").glob("*.html"))
    assert len(notebook_files) == 1
