"""The notebook renderer: the first concrete renderer built on top of
the Learning Intermediate Representation (``handbook.learning``).

Turns a ``Page`` into static HTML + CSS + SVG -- no JavaScript, no
Markdown, no framework -- proving the LIR is expressive enough to
produce something other than a Markdown document. See
``ARCHITECTURE_NOTES_NOTEBOOK.md`` at the repo root for the full
design rationale.

::

    from handbook.learning.examples import build_example_page
    from handbook.renderers.notebook import NotebookRenderer

    result = NotebookRenderer().render(build_example_page())
    result.write(Path("./out"))  # writes ./out/output.html
"""

from __future__ import annotations

from handbook.renderers.notebook.layout import LayoutEngine, LayoutPlan, LayoutRow
from handbook.renderers.notebook.renderer import NotebookRenderer
from handbook.renderers.notebook.result import RenderResult
from handbook.renderers.notebook.svg import SVGRenderer
from handbook.renderers.notebook.theme import NotebookTheme

__all__ = [
    "NotebookRenderer",
    "NotebookTheme",
    "LayoutEngine",
    "LayoutPlan",
    "LayoutRow",
    "SVGRenderer",
    "RenderResult",
]
