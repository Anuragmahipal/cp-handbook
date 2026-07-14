"""Integration tests: ``cp-handbook sync`` now also materializes
Algorithms/Patterns/Mistakes/Contests referenced by synced Problems
(``handbook.materialize``) and assembles them into one connected
notebook site with a dashboard (``handbook.sync.notebook_site``) --
without changing anything about ``compile_notebook_pages()``'s own,
pre-existing behavior (see ``test_sync_notebook_compilation.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

from handbook.sync.codeforces import CodeforcesClient
from handbook.sync.pipeline import run_sync


def _client(payloads: list[dict]) -> CodeforcesClient:
    response = {"status": "OK", "result": payloads}

    def _transport(url: str) -> bytes:
        return json.dumps(response).encode()

    return CodeforcesClient(transport=_transport)


def test_sync_materializes_the_algorithm_tag_on_a_synced_problem(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1, tags=("binary search",))])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert report.materialization is not None
    created_titles = {m.item.title for m in report.materialization.created}
    # handbook.sync.mapping title-cases CF tag names before they ever reach
    # a Relation -- materialization just uses whatever title it's handed.
    assert "Binary Search" in created_titles
    assert (vault_root / "Algorithms" / "binary-search.md").exists()


def test_sync_materializes_the_contest_the_problem_belongs_to(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1, contest_id=1868)])

    report = run_sync("someone", vault_root=vault_root, client=client)

    kinds_created = {m.item.KIND for m in report.materialization.created}
    assert "contest" in kinds_created
    assert (vault_root / "Contests" / "1868.md").exists()


def test_sync_builds_a_notebook_site_with_a_dashboard(vault_root: Path, cf_submission_payload):
    client = _client([cf_submission_payload(id=1, tags=("binary search",))])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert report.notebook_site is not None
    assert report.notebook_site.dashboard_path == vault_root / "Notebook" / "index.html"
    assert report.notebook_site.dashboard_path.exists()
    # both the Problem and the materialized Algorithm got a page
    kinds = {page.kind for page in report.notebook_site.pages}
    assert kinds == {"problem", "algorithm", "contest"}


def test_problem_page_links_to_its_materialized_algorithm(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1, tags=("binary search",))])

    report = run_sync("someone", vault_root=vault_root, client=client)

    problem_page = next(p for p in report.notebook_site.pages if p.kind == "problem")
    html = problem_page.html_path.read_text(encoding="utf-8")
    assert 'href="../Algorithms/binary-search.html"' in html


def test_running_sync_twice_does_not_recreate_or_duplicate_materialized_items(
    vault_root: Path, cf_submission_payload
):
    client = _client([cf_submission_payload(id=1, tags=("binary search",))])

    run_sync("someone", vault_root=vault_root, client=client)
    second_report = run_sync("someone", vault_root=vault_root, client=client)

    assert second_report.materialization.created == []
    assert list((vault_root / "Algorithms").glob("*.md")) == [
        vault_root / "Algorithms" / "binary-search.md"
    ]


def test_compile_notebook_pages_contract_is_unaffected_by_materialization(
    vault_root: Path, cf_submission_payload
):
    """`report.notebook_pages` -- the pre-existing, separately-tested
    contract from `compile_notebook_pages()` -- still reflects Problems
    only, exactly as before this chunk."""
    client = _client([cf_submission_payload(id=1, tags=("binary search",))])

    report = run_sync("someone", vault_root=vault_root, client=client)

    assert len(report.notebook_pages) == 1
    assert report.notebook_pages[0].kind == "problem"
