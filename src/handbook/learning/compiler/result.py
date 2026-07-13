"""``CompilationResult``: what compiling one ``KnowledgeItem`` produces.

Like :class:`~handbook.learning.compiler.context.CompilationContext`,
this is a plain dataclass rather than an LIR model -- ``page`` is the
actual LIR artifact; the rest is metadata *about* the compilation that
produced it, which has no business inside the renderer-independent
representation itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from handbook.learning.page import Page
from handbook.models.base import KnowledgeItem


@dataclass(frozen=True, slots=True)
class CompilationResult:
    """The output of compiling one ``KnowledgeItem`` into a ``Page``.

    Args:
        item: The source ``KnowledgeItem`` this ``page`` was compiled
            from -- kept alongside the result so a caller (the sync
            pipeline, a test, a CLI report) never has to re-thread it
            through separately.
        page: The compiled, renderer-independent LIR ``Page``. Ready to
            hand directly to any renderer (e.g.
            ``handbook.renderers.notebook.NotebookRenderer``) without
            further processing.
        warnings: Human-readable notes about content this compilation
            *could not* populate -- e.g. an empty ``implementation``
            field meant the "Implementation" section was omitted
            entirely, rather than rendered empty or invented. Never
            raised as errors: a sparse ``KnowledgeItem`` is expected
            and normal (a freshly-created note, a stub synced from
            Codeforces), and compiling it should always succeed with a
            correspondingly sparse ``Page`` -- these warnings exist so
            a caller *can* surface "this note could use more content"
            without the compiler ever refusing to produce a page.
    """

    item: KnowledgeItem
    page: Page
    warnings: list[str] = field(default_factory=list)
