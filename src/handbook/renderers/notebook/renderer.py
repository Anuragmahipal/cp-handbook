"""``NotebookRenderer``: the entry point of this package.

::

    NotebookRenderer(theme=NotebookTheme.light_notebook()).render(page)

turns one ``Page`` into a :class:`~handbook.renderers.notebook.result.
RenderResult` -- a standalone HTML document with its CSS already
inlined, openable directly in a browser with no server and no build
step. ``render_learning_path`` does the same for a ``LearningPath``, as
a simple ordered index rather than a full notebook layout, since a
path's steps are unresolved references (see
``handbook.learning.path.PathStep``) rather than full page content.

Deliberately not a subclass of ``handbook.core.renderer.Renderer``:
that interface is ``render(item: KnowledgeItem) -> str``, built for one
domain-model type producing one string. This renderer takes a
domain-independent ``Page`` and produces a multi-artifact
``RenderResult`` (html + css + assets) -- a different enough shape that
forcing a shared base class would mean bending one of the two
interfaces to fit the other for no real benefit. See
``ARCHITECTURE_NOTES_NOTEBOOK.md``.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from html import escape

from handbook.learning.page import Page, PageMetadata, Section
from handbook.learning.path import LearningPath, PathStep
from handbook.renderers.notebook import css_template
from handbook.renderers.notebook.blocks_html import (
    render_block,
    render_memory_anchor,
    render_review_badge,
    render_rich_text,
)
from handbook.renderers.notebook.layout import LayoutEngine, LayoutRow
from handbook.renderers.notebook.result import RenderResult
from handbook.renderers.notebook.svg import SVGRenderer
from handbook.renderers.notebook.theme import NotebookTheme


class NotebookRenderer:
    """Renders a ``Page`` (or a ``LearningPath``) as a static,
    self-contained HTML notebook page."""

    def __init__(self, theme: NotebookTheme | None = None) -> None:
        self._theme = theme or NotebookTheme.light_notebook()
        self._svg_renderer = SVGRenderer(self._theme)
        self._css = css_template.build(self._theme)
        self._layout_engine = LayoutEngine()

    def render(
        self, page: Page, *, learning_path: LearningPath | None = None
    ) -> RenderResult:
        """Render one ``Page``.

        If ``learning_path`` is given, a compact strip showing where
        this page sits in that path is rendered above the content --
        the current step highlighted, matched against ``page.id``.
        """
        plan = self._layout_engine.plan(page.sections)
        header = self._render_header(page.metadata)
        path_strip = (
            self._render_path_strip(learning_path, page) if learning_path else ""
        )
        diagram_counter = itertools.count()
        rows = "".join(self._render_row(row, diagram_counter) for row in plan.rows)
        body = (
            '<div class="lir-container">'
            f'<div class="lir-header">{header}</div>'
            f"{path_strip}{rows}"
            "</div>"
        )
        html = self._wrap_document(page.metadata.title, body)
        return RenderResult(title=page.metadata.title, html=html, css=self._css)

    def render_learning_path(self, path: LearningPath) -> RenderResult:
        """Render a ``LearningPath`` as a standalone ordered index of
        its steps. Steps are shown by their unresolved ``page_id`` /
        ``section_id`` references, not by pulling in the referenced
        pages' content -- see the package docstring for why.
        """
        description = (
            f'<p class="lir-summary">{escape(path.description)}</p>'
            if path.description
            else ""
        )
        steps = "".join(
            self._render_path_step(i, step)
            for i, step in enumerate(path.steps, start=1)
        )
        body = (
            '<div class="lir-container lir-path-page">'
            '<div class="lir-header">'
            f'<h1 class="lir-title">{escape(path.title)}</h1>{description}'
            "</div>"
            f'<div class="lir-path-steps">{steps}</div>'
            "</div>"
        )
        html = self._wrap_document(path.title, body)
        return RenderResult(title=path.title, html=html, css=self._css)

    # -- header / metadata --------------------------------------------

    def _render_header(self, metadata: PageMetadata) -> str:
        summary = (
            f'<p class="lir-summary">{escape(metadata.summary)}</p>'
            if metadata.summary
            else ""
        )
        chips: list[str] = []
        if metadata.source_kind:
            chips.append(
                '<span class="lir-meta-chip lir-meta-chip-accent">'
                f"{escape(metadata.source_kind)}</span>"
            )
        if metadata.difficulty:
            difficulty = escape(metadata.difficulty)
            chips.append(f'<span class="lir-meta-chip">{difficulty}</span>')
        if metadata.estimated_minutes:
            chips.append(
                f'<span class="lir-meta-chip">{metadata.estimated_minutes} min</span>'
            )
        for tag in metadata.tags:
            chips.append(f'<span class="lir-tag">#{escape(tag)}</span>')
        return (
            f'<h1 class="lir-title">{escape(metadata.title)}</h1>'
            f"{summary}"
            f'<div class="lir-metadata">{"".join(chips)}</div>'
        )

    def _render_path_strip(self, path: LearningPath, page: Page) -> str:
        steps: list[str] = []
        for i, step in enumerate(path.steps, start=1):
            is_current = step.page_id == page.id
            css_class = "lir-path-step"
            if is_current:
                css_class += " lir-path-step-current"
            page_id = escape(step.page_id)
            steps.append(f'<span class="{css_class}">{i}. {page_id}</span>')
        return (
            '<div class="lir-path-strip">'
            f"<strong>{escape(path.title)}:</strong>{''.join(steps)}"
            "</div>"
        )

    # -- rows / cards ---------------------------------------------------

    def _render_row(self, row: LayoutRow, diagram_counter: Iterator[int]) -> str:
        cards = "".join(
            self._render_card(section, diagram_counter) for section in row.sections
        )
        return f'<div class="lir-row">{cards}</div>'

    def _render_card(self, section: Section, diagram_counter: Iterator[int]) -> str:
        badges = "".join(render_review_badge(cue) for cue in section.review_cues)
        heading = (
            f'<h2 class="lir-section-heading">{render_rich_text(section.heading)}'
            f"{badges}</h2>"
        )
        blocks = "".join(
            render_block(b, self._svg_renderer, diagram_counter) for b in section.blocks
        )
        anchors = "".join(render_memory_anchor(a) for a in section.memory_anchors)
        return f'<div class="lir-card">{heading}{blocks}{anchors}</div>'

    def _render_path_step(self, index: int, step: PathStep) -> str:
        target = step.page_id
        if step.section_id:
            target = f"{target} \u00b7 {step.section_id}"
        optional = (
            '<span class="lir-path-optional">optional</span>' if step.optional else ""
        )
        rationale = ""
        if step.rationale:
            rationale = f'<p class="lir-text">{escape(step.rationale)}</p>'
        return (
            '<div class="lir-card lir-path-card">'
            f'<span class="lir-path-index">{index}</span>'
            "<div>"
            f'<div class="lir-section-heading">{escape(target)}{optional}</div>'
            f"{rationale}"
            "</div>"
            "</div>"
        )

    # -- document shell ---------------------------------------------------

    def _wrap_document(self, title: str, body: str) -> str:
        return (
            "<!doctype html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{escape(title)}</title>\n"
            f"<style>{self._css}</style>\n"
            "</head>\n"
            f'<body class="lir-page">\n{body}\n</body>\n'
            "</html>"
        )
