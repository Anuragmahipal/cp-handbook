"""``KnowledgeCompiler``: the public entry point of this package.

::

    from handbook.graph import GraphBuilder
    from handbook.learning.compiler import KnowledgeCompiler

    graph = GraphBuilder(items).build()
    compiler = KnowledgeCompiler(graph)
    result = compiler.compile(some_algorithm)
    result.page          # -> handbook.learning.page.Page
    result.warnings       # -> list[str]

Wires a :class:`~handbook.learning.compiler.context.CompilationContext`
around a :class:`~handbook.graph.KnowledgeGraph` and a
:class:`~handbook.learning.compiler.registry.CompilerRegistry`, the same
"one convenient facade over several small collaborators" shape
``handbook.handbook.Handbook`` already uses for folder resolution +
rendering + storage, and ``handbook.graph.graph.KnowledgeGraph`` uses
for index + traversal + export.
"""

from __future__ import annotations

from collections.abc import Iterable

from handbook.graph import KnowledgeGraph
from handbook.learning.compiler.context import CompilationContext
from handbook.learning.compiler.registry import CompilerRegistry, default_registry
from handbook.learning.compiler.result import CompilationResult
from handbook.models.base import KnowledgeItem


class KnowledgeCompiler:
    """Compiles ``KnowledgeItem`` instances into LIR ``Page``s, using a
    shared graph for every relationship-driven section.

    Args:
        graph: The knowledge graph to consult for every compilation --
            build it once (typically ``GraphBuilder(all_known_items).
            build()``) and reuse this ``KnowledgeCompiler`` across every
            item, so relation lookups stay O(edges touching that item)
            rather than rebuilding the graph per item. See
            ``docs/ARCHITECTURE_NOTES_COMPILER.md`` for the performance
            notes this is based on.
        registry: Which compiler handles which ``KnowledgeItem``
            subtype. Defaults to :func:`~handbook.learning.compiler.
            registry.default_registry`, covering ``Algorithm``,
            ``Problem``, ``Pattern``, ``Mistake``, ``Contest``.
    """

    def __init__(self, graph: KnowledgeGraph, *, registry: CompilerRegistry | None = None) -> None:
        self._graph = graph
        self._registry = registry if registry is not None else default_registry()

    def compile(self, item: KnowledgeItem) -> CompilationResult:
        """Compile one ``item`` into a :class:`~handbook.learning.
        compiler.result.CompilationResult`.

        Raises:
            handbook.learning.compiler.exceptions.
                UnsupportedKnowledgeTypeError: if no compiler is
                registered for ``type(item)`` (or any of its
                ancestors).
        """
        context = CompilationContext(graph=self._graph)
        return self._registry.compile(item, context)

    def compile_all(self, items: Iterable[KnowledgeItem]) -> list[CompilationResult]:
        """Compile every item in ``items``, in order.

        A thin convenience loop, not a batch optimization of its own --
        each call is independently O(that item's own relations) (see
        :meth:`compile`), so compiling a whole vault this way is
        already linear in the graph's total edge count, not quadratic.
        Propagates :class:`~handbook.learning.compiler.exceptions.
        UnsupportedKnowledgeTypeError` from the first unsupported item
        rather than silently skipping it -- a caller that wants to
        tolerate unsupported types (e.g. a ``Topic``) should filter
        ``items`` itself, or catch per-item by calling :meth:`compile`
        in its own loop instead.
        """
        return [self.compile(item) for item in items]
