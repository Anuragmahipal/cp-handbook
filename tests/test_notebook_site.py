"""Tests for handbook.sync.notebook_site.build_notebook_site."""

from __future__ import annotations

from pathlib import Path

from handbook.graph import GraphBuilder
from handbook.models import Algorithm, Mistake, Pattern, Platform, Problem, Relation, Topic
from handbook.sync.notebook_site import build_notebook_site


def _problem(title: str, **fields) -> Problem:
    fields.setdefault("platform", Platform.CODEFORCES)
    fields.setdefault("contest", "1868")
    fields.setdefault("index", "A")
    return Problem(title=title, **fields)


def test_writes_one_page_per_compilable_item_and_a_dashboard(vault_root: Path):
    p1 = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    algorithm = Algorithm(title="Binary Search")
    graph = GraphBuilder([p1, algorithm]).build()

    report = build_notebook_site(vault_root, [p1, algorithm], graph)

    assert len(report.pages) == 2
    kinds = {page.kind for page in report.pages}
    assert kinds == {"problem", "algorithm"}
    for page in report.pages:
        assert page.html_path.exists()
    assert report.dashboard_path == vault_root / "Notebook" / "index.html"
    assert report.dashboard_path.exists()


def test_unsupported_kinds_are_skipped_not_crashed_on(vault_root: Path):
    p1 = _problem("Candies")
    topic = Topic(title="Graphs 101")  # Topic compilation is out of scope for this chunk
    graph = GraphBuilder([p1, topic]).build()

    report = build_notebook_site(vault_root, [p1, topic], graph)

    kinds = {page.kind for page in report.pages}
    assert "topic" not in kinds


def test_lir_link_placeholders_become_real_cross_page_links(vault_root: Path):
    p1 = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    algorithm = Algorithm(title="Binary Search")
    graph = GraphBuilder([p1, algorithm]).build()

    report = build_notebook_site(vault_root, [p1, algorithm], graph)

    problem_page = next(p for p in report.pages if p.kind == "problem")
    html = problem_page.html_path.read_text(encoding="utf-8")
    assert '<span class="lir-link"' not in html
    assert 'href="../Algorithms/binary-search.html"' in html
    assert "Binary Search" in html


def test_unresolvable_relation_target_degrades_gracefully(vault_root: Path):
    # "Segment Tree" is referenced but never itself materialized/authored.
    p1 = _problem("Candies", algorithms=[Relation(target="Segment Tree")])
    graph = GraphBuilder([p1]).build()

    report = build_notebook_site(vault_root, [p1], graph)

    problem_page = next(p for p in report.pages if p.kind == "problem")
    html = problem_page.html_path.read_text(encoding="utf-8")
    assert "Segment Tree" in html  # still shown, just not linked
    assert 'href="../Algorithms/segment-tree.html"' not in html


def test_every_page_has_breadcrumbs_and_back_to_dashboard(vault_root: Path):
    p1 = _problem("Candies")
    graph = GraphBuilder([p1]).build()

    report = build_notebook_site(vault_root, [p1], graph)

    html = report.pages[0].html_path.read_text(encoding="utf-8")
    assert "site-breadcrumbs" in html
    assert "Back to Dashboard" in html
    assert 'href="../index.html"' in html


def test_prev_next_links_order_same_kind_items_alphabetically(vault_root: Path):
    p1 = _problem("Alpha Problem")
    p2 = _problem("Beta Problem")
    p3 = _problem("Charlie Problem")
    graph = GraphBuilder([p1, p2, p3]).build()

    report = build_notebook_site(vault_root, [p1, p2, p3], graph)

    beta_page = next(p for p in report.pages if p.title == "Beta Problem")
    html = beta_page.html_path.read_text(encoding="utf-8")
    assert "Alpha Problem" in html  # prev
    assert "Charlie Problem" in html  # next


def test_first_and_last_items_still_render_valid_prevnext_chrome(vault_root: Path):
    p1 = _problem("Alpha Problem")
    p2 = _problem("Beta Problem")
    graph = GraphBuilder([p1, p2]).build()

    report = build_notebook_site(vault_root, [p1, p2], graph)

    alpha_html = next(
        p for p in report.pages if p.title == "Alpha Problem"
    ).html_path.read_text(encoding="utf-8")
    beta_html = next(
        p for p in report.pages if p.title == "Beta Problem"
    ).html_path.read_text(encoding="utf-8")
    assert "site-pagenav-spacer" in alpha_html  # no "prev" for the first item
    assert "site-pagenav-spacer" in beta_html  # no "next" for the last item


def test_timeline_sidebar_present_and_chronological(vault_root: Path):
    older = _problem("Old One")
    newer = _problem("New One")
    graph = GraphBuilder([older, newer]).build()

    report = build_notebook_site(vault_root, [older, newer], graph)

    html = report.pages[0].html_path.read_text(encoding="utf-8")
    assert "Learning Timeline" in html
    older_pos = html.index("Old One", html.index("site-timeline-title"))
    newer_pos = html.index("New One", html.index("site-timeline-title"))
    assert older_pos < newer_pos  # chronological, oldest first


def test_dashboard_counts_reflect_materialized_kinds(vault_root: Path):
    p1 = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    p2 = _problem("Ropes", algorithms=[Relation(target="Binary Search")])
    algorithm = Algorithm(title="Binary Search")
    graph = GraphBuilder([p1, p2, algorithm]).build()

    report = build_notebook_site(vault_root, [p1, p2, algorithm], graph)

    dashboard_html = report.dashboard_path.read_text(encoding="utf-8")
    assert "Algorithms Learned" in dashboard_html
    assert "Binary Search (2×)" in dashboard_html  # live backlink count, not a stored counter


def test_breadcrumb_kind_link_resolves_to_a_real_dashboard_anchor(vault_root: Path):
    p1 = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    algorithm = Algorithm(title="Binary Search")
    graph = GraphBuilder([p1, algorithm]).build()

    report = build_notebook_site(vault_root, [p1, algorithm], graph)

    algorithm_page = next(p for p in report.pages if p.kind == "algorithm")
    page_html = algorithm_page.html_path.read_text(encoding="utf-8")
    assert '../index.html#algorithms' in page_html

    dashboard_html = report.dashboard_path.read_text(encoding="utf-8")
    assert 'id="algorithms"' in dashboard_html
    assert 'href="Algorithms/binary-search.html"' in dashboard_html


def test_weak_areas_ranks_mistakes_by_live_backlink_count(vault_root: Path):
    p1 = _problem("A", mistakes=[Relation(target="Off By One")])
    p2 = _problem("B", mistakes=[Relation(target="Off By One")])
    p3 = _problem("C", mistakes=[Relation(target="Wrong Data Type")])
    mistake_1 = Mistake(title="Off By One")
    mistake_2 = Mistake(title="Wrong Data Type")
    graph = GraphBuilder([p1, p2, p3, mistake_1, mistake_2]).build()

    report = build_notebook_site(vault_root, [p1, p2, p3, mistake_1, mistake_2], graph)

    dashboard_html = report.dashboard_path.read_text(encoding="utf-8")
    off_by_one_pos = dashboard_html.index("Off By One")
    wrong_type_pos = dashboard_html.index("Wrong Data Type")
    assert off_by_one_pos < wrong_type_pos  # 2 occurrences ranks above 1


def test_report_node_and_edge_counts_match_the_input_graph(vault_root: Path):
    p1 = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    algorithm = Algorithm(title="Binary Search")
    graph = GraphBuilder([p1, algorithm]).build()

    report = build_notebook_site(vault_root, [p1, algorithm], graph)

    assert report.node_count == len(graph)
    assert report.edge_count == len(graph.edges())


def test_build_notebook_site_is_safely_rerunnable(vault_root: Path):
    p1 = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    algorithm = Algorithm(title="Binary Search")
    graph = GraphBuilder([p1, algorithm]).build()

    build_notebook_site(vault_root, [p1, algorithm], graph)
    second_report = build_notebook_site(vault_root, [p1, algorithm], graph)

    assert len(second_report.pages) == 2
    for page in second_report.pages:
        assert page.html_path.exists()
