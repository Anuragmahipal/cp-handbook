"""Compiles every known ``KnowledgeItem`` into a notebook page as part of sync.

This is the "CLI integration" piece of the Knowledge -> LIR compiler
chunk (see ``docs/ARCHITECTURE_NOTES_COMPILER.md``): ``cp-handbook
sync`` should produce real, rendered notebook pages with no second
command to run. Every stage below calls straight into an *existing*
engine -- :class:`~handbook.learning.compiler.KnowledgeCompiler`,
:class:`~handbook.renderers.notebook.NotebookRenderer`,
:func:`~handbook.core.folders.resolve_folder` -- exactly the same
"orchestrate, don't reimplement" shape
:mod:`handbook.sync.pipeline` already follows for the rest of the sync
flow.

.. code-block:: text

    KnowledgeItem (Problem, today; any registered kind, generically)
        -> Page                 (KnowledgeCompiler, using the graph
                                  already rebuilt this run)
        -> RenderResult          (NotebookRenderer)
        -> Vault/Notebook/<Kind>/<slug>.html
                                  (same folder-naming convention as
                                  Handbook.store()'s Markdown notes,
                                  reused via resolve_folder())
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from handbook.core.folders import resolve_folder
from handbook.graph import KnowledgeGraph
from handbook.learning.compiler import KnowledgeCompiler, UnsupportedKnowledgeTypeError
from handbook.models.base import KnowledgeItem
from handbook.renderers.notebook import NotebookRenderer

_NOTEBOOK_ROOT = "Notebook"
"""Vault-relative root for compiled notebook pages -- a sibling of the
Markdown folders ``resolve_folder()`` already resolves (``Algorithms/``,
``Problems/``, ...), never mixed into them: a note's Markdown source
and its compiled notebook rendering are two different artifacts of the
same knowledge, not one file with two meanings.
"""


@dataclass(frozen=True, slots=True)
class CompiledNotebookPage:
    """One item's compiled-and-rendered notebook page: everything the
    CLI needs to report on it."""

    item_id: str
    title: str
    kind: str
    html_path: Path
    warnings: list[str] = field(default_factory=list)


def compile_notebook_pages(
    vault_root: Path, items: Iterable[KnowledgeItem], graph: KnowledgeGraph
) -> list[CompiledNotebookPage]:
    """Compile and render every item in ``items`` this chunk's compiler
    supports, writing each to ``<vault_root>/Notebook/<Kind>/<slug>.html``.

    Cheap enough to run over *every* known item on *every* sync run --
    the same "rebuild from the full known set, not just this run's
    delta" choice :mod:`handbook.sync.pipeline` already makes for the
    graph itself (see ``DEVELOPER_NOTES_SYNC.md``): compilation is a
    pure, linear-in-relations function of ``(item, graph)`` (see
    ``handbook.learning.compiler.helpers``' module docstring on
    determinism), and rendering one page is plain string/SVG
    construction with no I/O until the final write -- see
    ``docs/ARCHITECTURE_NOTES_COMPILER.md`` for the performance notes
    this is based on.

    Items of a kind this chunk's compiler doesn't (yet) cover -- e.g. a
    future ``Topic`` -- are skipped, not fatal: sync only ever produces
    ``Problem`` items today (see ``DEVELOPER_NOTES_SYNC.md``'s "Known
    simplifications"), and this function is written generically against
    whatever ``items`` actually contains so that the day sync (or any
    other future producer) starts creating ``Algorithm``/``Pattern``/
    ``Mistake`` notes, they're compiled here with zero changes to this
    function.
    """
    compiler = KnowledgeCompiler(graph)
    renderer = NotebookRenderer()
    pages: list[CompiledNotebookPage] = []

    for item in items:
        try:
            result = compiler.compile(item)
        except UnsupportedKnowledgeTypeError:
            continue

        rendered = renderer.render(result.page)
        directory = vault_root / _NOTEBOOK_ROOT / resolve_folder(item)
        html_path = rendered.write(directory, filename=f"{item.slug}.html")

        pages.append(
            CompiledNotebookPage(
                item_id=item.id,
                title=item.title,
                kind=item.kind,
                html_path=html_path,
                warnings=result.warnings,
            )
        )

    return pages
