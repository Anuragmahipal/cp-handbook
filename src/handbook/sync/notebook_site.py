"""Turns a set of independently-compiled notebook pages into one
connected site: real cross-page links, breadcrumbs/prev/next/back-to-
dashboard navigation, a shared learning-timeline sidebar on every page,
and a ``Notebook/index.html`` dashboard tying it all together.

Why this is a separate module from :mod:`handbook.sync.notebook`
-------------------------------------------------------------------
:func:`handbook.sync.notebook.compile_notebook_pages` already does the
"compile every known item, render it, write it" loop, and has its own
tests + a golden-snapshot contract that depend on its output being
exactly what :class:`~handbook.renderers.notebook.NotebookRenderer`
alone produces. This module needs to do something meaningfully
different to that same output *before* it's written: rewrite the
inert ``<span class="lir-link">`` placeholders
(``handbook.renderers.notebook.blocks_html`` -- see its module
docstring on why a single-page renderer can't already know another
page's URL) into real ``<a href>``s once every other page's location
is known, and wrap the page in shared site chrome. Rather than bend
``compile_notebook_pages()`` into two modes, this module calls the same
two building blocks it does (``KnowledgeCompiler``, ``NotebookRenderer``)
itself and post-processes their output -- "do not redesign
NotebookRenderer" means exactly this: read its already-public output
(``RenderResult.html``/``.css``), never its internals.

.. code-block:: text

    items (Problems + materialized Algorithms/Patterns/Mistakes/Contests)
        -> KnowledgeCompiler + NotebookRenderer   (unchanged, reused)
        -> link map                                (item id -> page URL)
        -> per-page chrome                         (linkify + breadcrumbs
                                                      + prev/next + shared
                                                      timeline sidebar)
        -> Notebook/<Kind>/<slug>.html
        -> Notebook/index.html                     (dashboard)

Both this module's per-page writes and its dashboard are cheap to
regenerate wholesale on every run -- the same "recompute the *rendered*
view from scratch every time, never hand-patch it" reasoning
``docs/ARCHITECTURE_NOTES_COMPILER.md`` already established for
``compile_notebook_pages()``. Nothing this module writes is a source of
truth; the vault's Markdown notes are. That's what lets "``cp-handbook
sync`` never regenerates blindly" hold at the level that actually
matters (a person's notes are never touched here) without this module
having to invent incremental HTML patching for views that have no state
of their own.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path

from handbook.core.folders import resolve_folder
from handbook.graph import KnowledgeGraph
from handbook.evolution.events import EventKind
from handbook.evolution.log import EvolutionLog
from handbook.evolution.stats import personal_statistics
from handbook.learning.compiler import KnowledgeCompiler, UnsupportedKnowledgeTypeError
from handbook.learning.enums import ReviewStatus
from handbook.learning.page import Page
from handbook.models import Problem
from handbook.models.base import KnowledgeItem
from handbook.renderers.notebook import NotebookRenderer
from handbook.renderers.notebook.result import RenderResult
from handbook.utils.filesystem import atomic_write

_NOTEBOOK_ROOT = "Notebook"
_DASHBOARD_FILENAME = "index.html"
_TIMELINE_EVENT_LIMIT = 60
_DASHBOARD_LIST_LIMIT = 8


# == public result shapes =====================================================


@dataclass(frozen=True, slots=True)
class NotebookSitePage:
    """One item's final, site-integrated notebook page."""

    item_id: str
    title: str
    kind: str
    html_path: Path
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class NotebookSiteReport:
    """Everything the CLI needs to report on one ``build_notebook_site()`` run."""

    pages: list[NotebookSitePage] = field(default_factory=list)
    dashboard_path: Path | None = None
    node_count: int = 0
    edge_count: int = 0
    warnings: list[str] = field(default_factory=list)


# == internal working shapes ==================================================


@dataclass(frozen=True, slots=True)
class _CompiledEntry:
    item: KnowledgeItem
    page: Page
    rendered: RenderResult
    warnings: list[str]
    folder: str

    @property
    def rel_path(self) -> str:
        """This page's path relative to the ``Notebook/`` root, e.g.
        ``"Algorithms/binary-search.html"`` -- what the dashboard links
        to directly, and what every other page links to via a leading
        ``"../"``."""
        return f"{self.folder}/{self.item.slug}.html"


@dataclass(frozen=True, slots=True)
class _TimelineEvent:
    when: datetime
    label: str
    rel_path: str | None


def build_notebook_site(
    vault_root: Path,
    items: Sequence[KnowledgeItem],
    graph: KnowledgeGraph,
    *,
    evolution: EvolutionLog | None = None,
) -> NotebookSiteReport:
    """Compile, link, and write one connected notebook site for every
    item in ``items`` this chunk's compiler supports, plus a dashboard
    at ``<vault_root>/Notebook/index.html``.

    ``items`` is expected to be the *full* known set for this run --
    typically a vault's Problems plus whatever
    :class:`~handbook.materialize.engine.MaterializationEngine` handed
    back -- and ``graph`` a graph already built over that same set, so
    that every relation resolves to a real node rather than a shadow
    (see ``handbook.materialize`` for why that matters). Items of a
    kind the compiler doesn't support are silently skipped, same as
    :func:`handbook.sync.notebook.compile_notebook_pages`.

    Args:
        evolution: This vault's learning history
            (:mod:`handbook.evolution`), if any. Forwarded into every
            page's compilation (so ``AlgorithmCompiler``'s evolution-
            stats sections and every compiler's Learning History
            section can render) and into the dashboard's Personal
            Statistics card. ``None`` (the default) reproduces this
            function's exact pre-evolution behavior -- every existing
            caller of this function keeps working unchanged.
    """
    entries = _compile_all(items, graph, evolution)
    warnings: list[str] = []

    link_map = {entry.item.id: entry.rel_path for entry in entries}
    nav_index = _build_nav_index(entries)
    timeline_events = _timeline_events(entries, link_map)

    pages: list[NotebookSitePage] = []
    notebook_root = vault_root / _NOTEBOOK_ROOT
    for entry in entries:
        nav_group, position = nav_index[entry.item.id]
        page_html = _render_page_chrome(
            entry,
            link_map=link_map,
            nav_group=nav_group,
            position=position,
            timeline_html=_render_timeline(timeline_events, href_prefix="../"),
        )
        html_path = notebook_root / entry.folder / f"{entry.item.slug}.html"
        atomic_write(html_path, page_html)
        pages.append(
            NotebookSitePage(
                item_id=entry.item.id,
                title=entry.item.title,
                kind=entry.item.kind,
                html_path=html_path,
                warnings=entry.warnings,
            )
        )

    dashboard_html = _render_dashboard(
        entries,
        graph,
        timeline_html=_render_timeline(timeline_events, href_prefix=""),
        evolution=evolution,
    )
    dashboard_path = notebook_root / _DASHBOARD_FILENAME
    atomic_write(dashboard_path, dashboard_html)

    return NotebookSiteReport(
        pages=pages,
        dashboard_path=dashboard_path,
        node_count=len(graph),
        edge_count=len(graph.edges()),
        warnings=warnings,
    )


# == compilation ===============================================================


def _compile_all(
    items: Sequence[KnowledgeItem], graph: KnowledgeGraph, evolution: EvolutionLog | None = None
) -> list[_CompiledEntry]:
    items_by_id = {item.id: item for item in items}
    compiler = KnowledgeCompiler(graph, evolution=evolution, items_by_id=items_by_id)
    renderer = NotebookRenderer()
    entries: list[_CompiledEntry] = []
    for item in items:
        try:
            result = compiler.compile(item)
        except UnsupportedKnowledgeTypeError:
            continue
        rendered = renderer.render(result.page)
        entries.append(
            _CompiledEntry(
                item=item,
                page=result.page,
                rendered=rendered,
                warnings=result.warnings,
                folder=resolve_folder(item),
            )
        )
    return entries


# == navigation: breadcrumbs / prev / next / back to dashboard ===============


def _build_nav_index(
    entries: Sequence[_CompiledEntry],
) -> dict[str, tuple[list[_CompiledEntry], int]]:
    """For every item id, which ordered group (by folder, alphabetical
    by title) it belongs to and its position in that group -- what
    prev/next chrome needs.
    """
    by_folder: dict[str, list[_CompiledEntry]] = {}
    for entry in entries:
        by_folder.setdefault(entry.folder, []).append(entry)
    for group in by_folder.values():
        group.sort(key=lambda e: e.item.title.lower())

    index: dict[str, tuple[list[_CompiledEntry], int]] = {}
    for group in by_folder.values():
        for position, entry in enumerate(group):
            index[entry.item.id] = (group, position)
    return index


def _render_breadcrumbs(entry: _CompiledEntry) -> str:
    return (
        '<nav class="site-breadcrumbs" aria-label="Breadcrumb">'
        '<a href="../index.html">Notebook</a>'
        '<span class="site-crumb-sep">/</span>'
        f'<a href="../index.html#{escape(entry.folder.lower(), quote=True)}">'
        f"{escape(entry.folder)}</a>"
        '<span class="site-crumb-sep">/</span>'
        f'<span aria-current="page">{escape(entry.item.title)}</span>'
        "</nav>"
    )


def _render_prev_next(nav_group: list[_CompiledEntry], position: int) -> str:
    parts = ['<nav class="site-pagenav" aria-label="Page navigation">']
    if position > 0:
        prev_entry = nav_group[position - 1]
        parts.append(
            '<a class="site-pagenav-prev" href="../'
            f'{escape(prev_entry.rel_path, quote=True)}">'
            f"&larr; {escape(prev_entry.item.title)}</a>"
        )
    else:
        parts.append('<span class="site-pagenav-spacer"></span>')

    parts.append('<a class="site-pagenav-home" href="../index.html">Back to Dashboard</a>')

    if position < len(nav_group) - 1:
        next_entry = nav_group[position + 1]
        parts.append(
            '<a class="site-pagenav-next" href="../'
            f'{escape(next_entry.rel_path, quote=True)}">'
            f"{escape(next_entry.item.title)} &rarr;</a>"
        )
    else:
        parts.append('<span class="site-pagenav-spacer"></span>')
    parts.append("</nav>")
    return "".join(parts)


# == cross-page linkification ==================================================

_LINK_SPAN_RE = re.compile(r'<span class="lir-link" title="([^"]*)">(.*?)</span>', re.DOTALL)
_BODY_OPEN_RE = re.compile(r'<body class="lir-page">\n')
_BODY_CLOSE = "\n</body>"


def _linkify(html_fragment: str, link_map: dict[str, str], *, href_prefix: str) -> str:
    """Rewrite every inert ``lir-link`` placeholder span into a real
    ``<a href>`` when its target resolved to a compiled page this run;
    left as plain (unlinked) text otherwise -- e.g. a relation naming
    something that isn't itself in the vault. Graceful degradation, not
    an error: a compiler-level ``related_pairs()`` already treats a
    missing far side as "nothing to show" (see
    ``handbook.learning.compiler.helpers``); a missing link target here
    is the same idea one layer up.
    """

    def _substitute(match: re.Match[str]) -> str:
        target_id = match.group(1)
        inner_text = match.group(2)
        rel_path = link_map.get(target_id)
        if rel_path is None:
            return match.group(0)
        href = escape(f"{href_prefix}{rel_path}", quote=True)
        return f'<a class="lir-link" href="{href}">{inner_text}</a>'

    return _LINK_SPAN_RE.sub(_substitute, html_fragment)


def _extract_body(html: str) -> str | None:
    """Pull the inner content out of a ``RenderResult.html`` standalone
    document, so it can be re-wrapped in site chrome. Returns ``None``
    if the document doesn't match ``NotebookRenderer``'s current shell
    format -- see :func:`_page_content` for the fallback.
    """
    match = _BODY_OPEN_RE.search(html)
    if match is None:
        return None
    start = match.end()
    end = html.rfind(_BODY_CLOSE)
    if end == -1 or end < start:
        return None
    return html[start:end]


def _page_content(rendered: RenderResult, link_map: dict[str, str], *, href_prefix: str) -> str:
    body = _extract_body(rendered.html)
    if body is None:
        # Defensive fallback only -- would trigger if NotebookRenderer's
        # document shell (`_wrap_document`) ever changes shape. Keeps
        # the site buildable (a page still opens, just without
        # cross-page linkification or shared chrome around its
        # content) rather than crashing the whole sync run over one
        # page's markup.
        safe = escape(rendered.html, quote=True)
        return f'<iframe class="site-page-fallback" srcdoc="{safe}"></iframe>'
    return _linkify(body, link_map, href_prefix=href_prefix)


# == the shared learning timeline =============================================


def _timeline_events(
    entries: Sequence[_CompiledEntry], link_map: dict[str, str]
) -> list[_TimelineEvent]:
    """One event per item, in chronological order -- the vault's own
    history. For Problems, the timestamp is ``solved_at`` (or
    ``first_attempted_at`` for unsolved), not ``created_at``, so the
    timeline reflects when the user actually solved the problem on
    Codeforces, not when sync ran.
    """
    events: list[_TimelineEvent] = []
    for entry in entries:
        item = entry.item
        rel_path = link_map.get(item.id)
        label = _timeline_label(entry)
        if label is None:
            continue

        # Use historical timestamps for Problems
        if item.kind == "problem" and hasattr(item, "solved_at"):
            if item.solved_at is not None:
                when = item.solved_at
            elif hasattr(item, "first_attempted_at") and item.first_attempted_at is not None:
                when = item.first_attempted_at
            else:
                when = item.created_at
        else:
            when = item.created_at

        events.append(_TimelineEvent(when=when, label=label, rel_path=rel_path))
    events.sort(key=lambda event: event.when)
    return events


def _timeline_label(entry: _CompiledEntry) -> str | None:
    item = entry.item
    kind = item.kind
    if kind == "problem":
        solved = getattr(item, "solved", True)
        return f"{'Solved' if solved else 'Attempted'} {item.title}"
    if kind == "mistake":
        return f"Recorded mistake: {item.title}"
    if kind in ("algorithm", "pattern"):
        return f"Learned {item.title}"
    if kind == "contest":
        return f"Contest: {item.title}"
    return None


def _render_timeline(events: Sequence[_TimelineEvent], *, href_prefix: str) -> str:
    trimmed = events[-_TIMELINE_EVENT_LIMIT:]
    parts = ['<div class="site-timeline-title">Learning Timeline</div>']
    if not trimmed:
        parts.append('<p class="site-timeline-empty">Nothing recorded yet.</p>')
        return "".join(parts)

    current_month = None
    for event in trimmed:
        month_label = event.when.strftime("%B %Y")
        if month_label != current_month:
            parts.append(f'<div class="site-timeline-month">{escape(month_label)}</div>')
            current_month = month_label
        if event.rel_path:
            href = escape(f"{href_prefix}{event.rel_path}", quote=True)
            parts.append(
                f'<a class="site-timeline-event" href="{href}">{escape(event.label)}</a>'
            )
        else:
            parts.append(f'<div class="site-timeline-event">{escape(event.label)}</div>')
    return "".join(parts)


# == per-page assembly =========================================================


def _render_page_chrome(
    entry: _CompiledEntry,
    *,
    link_map: dict[str, str],
    nav_group: list[_CompiledEntry],
    position: int,
    timeline_html: str,
) -> str:
    content = _page_content(entry.rendered, link_map, href_prefix="../")
    breadcrumbs = _render_breadcrumbs(entry)
    prev_next = _render_prev_next(nav_group, position)
    title = escape(f"{entry.item.title} · CP Notebook")
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f"<style>{entry.rendered.css}{_SITE_CSS}</style>\n"
        "</head>\n"
        '<body class="site-body">\n'
        '<div class="site-shell">\n'
        f'<aside class="site-sidebar" aria-label="Learning timeline">{timeline_html}</aside>\n'
        '<div class="site-main">\n'
        f"{breadcrumbs}\n"
        f'<div class="site-page-content">{content}</div>\n'
        f"{prev_next}\n"
        "</div>\n"
        "</div>\n"
        "</body>\n"
        "</html>"
    )


# == dashboard ==================================================================


def _backlinks(graph: KnowledgeGraph, item_id: str, *, field_name: str) -> int:
    """How many other items point at ``item_id`` via ``field_name`` --
    the live, always-fresh "how often is this actually used" count (see
    ``handbook.materialize.engine`` module docstring on why this is
    preferred over any stored counter field).
    """
    if graph.get(item_id) is None:
        return 0
    provenance = f"field:{field_name}"
    return sum(
        1
        for edge, _node in graph.related(item_id, direction="in")
        if edge.provenance == provenance
    )


def _review_queue(entries: Sequence[_CompiledEntry]) -> list[tuple[str, str]]:
    """``(item title, section heading)`` pairs for every review cue
    currently due, across every compiled page."""
    due: list[tuple[str, str]] = []
    for entry in entries:
        for section in entry.page.sections:
            for cue in section.review_cues:
                if cue.status == ReviewStatus.DUE:
                    due.append((entry.item.title, section.heading.as_plain_text()))
    return due


def _mastery_breakdown(entries: Sequence[_CompiledEntry]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for entry in entries:
        for section in entry.page.sections:
            for cue in section.review_cues:
                counts[cue.status.value] += 1
    return counts


def _stat_card(label: str, value: object) -> str:
    return (
        '<div class="site-stat-card">'
        f'<div class="site-stat-value">{escape(str(value))}</div>'
        f'<div class="site-stat-label">{escape(label)}</div>'
        "</div>"
    )


def _linked_list(items: Sequence[tuple[str, str]]) -> str:
    """``items`` is a sequence of ``(label, href)`` -- href may be
    empty for a plain, unlinked line."""
    if not items:
        return '<p class="site-empty">Nothing here yet.</p>'
    lines = []
    for label, href in items:
        if href:
            lines.append(f'<li><a href="{escape(href, quote=True)}">{escape(label)}</a></li>')
        else:
            lines.append(f"<li>{escape(label)}</li>")
    return f'<ul class="site-list">{"".join(lines)}</ul>'


def _render_browse_by_kind(entries: Sequence[_CompiledEntry]) -> str:
    """Every compiled page, grouped by folder/kind, each group anchored
    at ``id="{folder.lower()}"`` -- what a page's breadcrumb (``Notebook
    / <Kind> / <Title>``) actually links its middle segment to, and the
    only place in the dashboard that lists *every* page rather than a
    top-N slice.
    """
    by_folder: dict[str, list[_CompiledEntry]] = {}
    for entry in entries:
        by_folder.setdefault(entry.folder, []).append(entry)

    cards = []
    for folder in sorted(by_folder):
        group = sorted(by_folder[folder], key=lambda e: e.item.title.lower())
        list_html = _linked_list([(e.item.title, e.rel_path) for e in group])
        cards.append(
            f'<section class="site-dashboard-card" id="{escape(folder.lower(), quote=True)}">'
            f"<h2>{escape(folder)} ({len(group)})</h2>{list_html}</section>"
        )
    return "".join(cards)


def _render_personal_statistics(
    problems: Sequence[Problem], algorithm_count: int, evolution: EvolutionLog | None
) -> str:
    """Part 3's "Personal Statistics" dashboard card. Empty string
    (nothing rendered) when no evolution log was supplied -- same
    "omit rather than pad" rule as everywhere else this chunk touches.
    """
    if evolution is None:
        return ""
    growth_events = sum(1 for event in evolution.events() if event.kind == EventKind.KNOWLEDGE_GROWTH)
    stats = personal_statistics(
        problems, algorithm_count=algorithm_count, knowledge_growth_events=growth_events
    )

    lines = [
        f"Average rating: {stats.average_rating if stats.average_rating is not None else 'n/a'}",
        f"Rating growth: {_format_signed(stats.rating_growth)}",
        f"Algorithms learned: {stats.algorithms_learned}",
        f"Weekly solves: {stats.weekly_solves}",
        f"Monthly solves: {stats.monthly_solves}",
        f"Current solve streak: {stats.current_streak_days} day(s) "
        f"(longest: {stats.longest_streak_days})",
        f"Knowledge growth events recorded: {stats.knowledge_growth_events}",
    ]
    if stats.topic_distribution:
        top = ", ".join(f"{name} ({count}×)" for name, count in stats.topic_distribution[:5])
        lines.append(f"Topic distribution: {top}")

    items_html = "".join(f"<li>{escape(line)}</li>" for line in lines)
    return (
        '<section class="site-dashboard-card" id="personal-statistics">'
        "<h2>Personal Statistics</h2>"
        f'<ul class="site-list">{items_html}</ul>'
        "</section>"
    )


def _format_signed(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value}"


def _render_dashboard(
    entries: Sequence[_CompiledEntry],
    graph: KnowledgeGraph,
    *,
    timeline_html: str,
    evolution: EvolutionLog | None = None,
) -> str:
    counts = Counter(entry.item.kind for entry in entries)
    problems = [e for e in entries if e.item.kind == "problem"]
    algorithms = [e for e in entries if e.item.kind == "algorithm"]
    mistakes = [e for e in entries if e.item.kind == "mistake"]
    solved = [e for e in problems if getattr(e.item, "solved", True)]

    stats_html = "".join(
        [
            _stat_card("Algorithms Learned", counts.get("algorithm", 0)),
            _stat_card("Patterns Learned", counts.get("pattern", 0)),
            _stat_card("Mistakes Recorded", counts.get("mistake", 0)),
            _stat_card("Problems Solved", len(solved)),
        ]
    )

    recently_solved = sorted(
        (e for e in problems if getattr(e.item, "solved", True)),
        key=lambda e: getattr(e.item, "solved_at", e.item.created_at) or e.item.created_at,
        reverse=True,
    )[:_DASHBOARD_LIST_LIMIT]
    recently_solved_html = _linked_list([(e.item.title, e.rel_path) for e in recently_solved])

    # Upsolve: unsolved problems ordered by attempts, rating, recency
    unsolved = sorted(
        (e for e in problems if not getattr(e.item, "solved", True)),
        key=lambda e: (
            -getattr(e.item, "attempt_count", 0),
            -(e.item.rating or 0),
            -(getattr(e.item, "first_attempted_at", e.item.created_at) or e.item.created_at).timestamp(),
        ),
    )[:_DASHBOARD_LIST_LIMIT]
    upsolve_html = _linked_list([(e.item.title, e.rel_path) for e in unsolved])
    weak_areas = sorted(
        mistakes,
        key=lambda e: _backlinks(graph, e.item.id, field_name="mistakes"),
        reverse=True,
    )[:_DASHBOARD_LIST_LIMIT]
    weak_areas_html = _linked_list(
        [
            (
                f"{e.item.title} ({_backlinks(graph, e.item.id, field_name='mistakes')}×)",
                e.rel_path,
            )
            for e in weak_areas
            if _backlinks(graph, e.item.id, field_name="mistakes") > 0
        ]
    )

    most_used = sorted(
        algorithms,
        key=lambda e: _backlinks(graph, e.item.id, field_name="algorithms"),
        reverse=True,
    )[:_DASHBOARD_LIST_LIMIT]
    most_used_html = _linked_list(
        [
            (
                f"{e.item.title} ({_backlinks(graph, e.item.id, field_name='algorithms')}×)",
                e.rel_path,
            )
            for e in most_used
            if _backlinks(graph, e.item.id, field_name="algorithms") > 0
        ]
    )

    review_queue = _review_queue(entries)[:_DASHBOARD_LIST_LIMIT]
    review_queue_html = _linked_list(
        [(f"{title} — {heading}", "") for title, heading in review_queue]
    )

    mastery = _mastery_breakdown(entries)
    mastery_line = (
        ", ".join(
            f"{count} {status}" for status, count in sorted(mastery.items(), key=lambda kv: -kv[1])
        )
        or "No review cues recorded yet."
    )

    graph_summary = f"{len(graph)} nodes / {len(graph.edges())} edges — " + ", ".join(
        f"{count} {kind}" for kind, count in sorted(counts.items())
    )

    sections_html = "".join(
        f'<section class="site-dashboard-card" id="{escape(section_id, quote=True)}">'
        f"<h2>{escape(heading)}</h2>{body}</section>"
        for section_id, heading, body in [
            ("recently-solved", "Recently Solved", recently_solved_html),
        ("upsolve", "Upsolve", upsolve_html),
            ("weak-areas", "Weak Areas", weak_areas_html),
            ("most-used-algorithms", "Most Used Algorithms", most_used_html),
            ("review-queue", "Review Queue", review_queue_html),
        ]
    )

    browse_html = _render_browse_by_kind(entries)
    personal_stats_html = _render_personal_statistics(
        [e.item for e in problems if isinstance(e.item, Problem)], len(algorithms), evolution
    )

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>CP Notebook · Dashboard</title>\n"
        f"<style>{_SITE_CSS}</style>\n"
        "</head>\n"
        '<body class="site-body">\n'
        '<div class="site-shell">\n'
        f'<aside class="site-sidebar" aria-label="Learning timeline">{timeline_html}</aside>\n'
        '<div class="site-main">\n'
        '<h1 class="site-dashboard-title">Notebook</h1>\n'
        f'<div class="site-stat-grid">{stats_html}</div>\n'
        f"{personal_stats_html}\n"
        f"{sections_html}\n"
        f"{browse_html}\n"
        '<section class="site-dashboard-card">'
        f"<h2>Mastery</h2><p>{escape(mastery_line)}</p></section>"
        '<section class="site-dashboard-card">'
        f"<h2>Knowledge Graph Summary</h2><p>{escape(graph_summary)}</p></section>\n"
        "</div>\n"
        "</div>\n"
        "</body>\n"
        "</html>"
    )


# == site chrome CSS ============================================================
# Independent of NotebookTheme/css_template.py on purpose -- this styles
# the *shell* around a rendered page (sidebar, breadcrumbs, dashboard
# cards), never a page's own content, so it has no reason to reach into
# the renderer's internals to build it. Loosely matches the same warm,
# paper-like palette `NotebookTheme.light_notebook()` uses, so the two
# don't visually clash, without importing or depending on it.

_SITE_CSS = """
.site-body { margin: 0; background: #efe9da; font-family: 'Iowan Old Style', Georgia, serif; }
.site-shell { display: flex; align-items: flex-start; min-height: 100vh; }
.site-sidebar {
  width: 260px; flex-shrink: 0; box-sizing: border-box; padding: 1.5rem 1rem;
  background: #2b2620; color: #ece6d8; min-height: 100vh; position: sticky; top: 0;
  overflow-y: auto; font-size: 0.85rem;
}
.site-timeline-title { font-weight: bold; letter-spacing: 0.04em; text-transform: uppercase;
  font-size: 0.75rem; color: #c65d2e; margin-bottom: 0.75rem; }
.site-timeline-month { margin-top: 0.9rem; font-weight: bold; color: #948b7a; }
.site-timeline-event { display: block; padding: 0.15rem 0 0.15rem 0.6rem; color: #ece6d8;
  text-decoration: none; border-left: 2px solid #4a443a; }
a.site-timeline-event:hover { border-left-color: #c65d2e; color: #e08a52; }
.site-timeline-empty { color: #948b7a; }
.site-main { flex: 1; min-width: 0; padding: 1.75rem 2.5rem 3rem; box-sizing: border-box; }
.site-breadcrumbs { font-size: 0.85rem; color: #8a8172; margin-bottom: 1rem; }
.site-breadcrumbs a { color: #8a8172; }
.site-crumb-sep { margin: 0 0.4em; }
.site-page-content { margin-bottom: 1.5rem; }
.site-pagenav { display: flex; justify-content: space-between; align-items: center;
  border-top: 1px solid #e4ddc9; padding-top: 1rem; gap: 1rem; }
.site-pagenav a { color: #c65d2e; text-decoration: none; font-size: 0.9rem; }
.site-pagenav a:hover { text-decoration: underline; }
.site-pagenav-home { font-weight: bold; }
.site-pagenav-spacer { flex: 1; }
a.lir-link { color: #c65d2e; text-decoration: none; border-bottom: 1px dotted #c65d2e; }
a.lir-link:hover { border-bottom-style: solid; }
.site-dashboard-title { font-size: 2rem; margin: 0 0 1rem; color: #2b2620; }
.site-stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1rem; margin-bottom: 1.5rem; }
.site-stat-card { background: #fff; border: 1px solid #e4ddc9; border-radius: 8px;
  padding: 1rem; text-align: center; }
.site-stat-value { font-size: 1.8rem; font-weight: bold; color: #c65d2e; }
.site-stat-label { font-size: 0.8rem; color: #8a8172; margin-top: 0.25rem; }
.site-dashboard-card { background: #fff; border: 1px solid #e4ddc9; border-radius: 8px;
  padding: 1.25rem 1.5rem; margin-bottom: 1rem; }
.site-dashboard-card h2 { margin-top: 0; font-size: 1.1rem; color: #2b2620; }
.site-list { list-style: none; margin: 0; padding: 0; }
.site-list li { padding: 0.3rem 0; border-bottom: 1px solid #f0ebdc; }
.site-list a { color: #2b2620; text-decoration: none; }
.site-list a:hover { color: #c65d2e; }
.site-empty { color: #8a8172; font-style: italic; }
.site-page-fallback { width: 100%; height: 80vh; border: 1px solid #e4ddc9; }
"""
