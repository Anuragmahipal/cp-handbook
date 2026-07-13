"""``CompilerRegistry``: dispatches a ``KnowledgeItem`` to its compiler.

Keyed by exact class, resolved by walking the item's MRO -- exactly the
convention ``handbook.core.folders._FOLDER_MAP``/``resolve_folder``
already established for mapping a knowledge type to a vault folder.
Reusing that convention here (rather than inventing a second dispatch
mechanism) is what "connect them, don't redesign" means in practice.
"""

from __future__ import annotations

from handbook.learning.compiler.algorithm import AlgorithmCompiler
from handbook.learning.compiler.base import Compiler
from handbook.learning.compiler.context import CompilationContext
from handbook.learning.compiler.contest import ContestCompiler
from handbook.learning.compiler.exceptions import UnsupportedKnowledgeTypeError
from handbook.learning.compiler.mistake import MistakeCompiler
from handbook.learning.compiler.pattern import PatternCompiler
from handbook.learning.compiler.problem import ProblemCompiler
from handbook.learning.compiler.result import CompilationResult
from handbook.models.base import KnowledgeItem


class CompilerRegistry:
    """A mutable registry of ``KnowledgeItem`` subtype -> ``Compiler``.

    Usage::

        registry = CompilerRegistry()
        registry.register(Algorithm, AlgorithmCompiler())
        registry.compile(some_algorithm, context)

    or, for the five kinds this chunk implements, just
    :func:`default_registry`.
    """

    def __init__(self) -> None:
        self._compilers: dict[type[KnowledgeItem], Compiler] = {}

    def register(self, item_type: type[KnowledgeItem], compiler: Compiler) -> None:
        """Register ``compiler`` as the handler for exactly ``item_type``.

        Registering a second compiler for the same ``item_type``
        replaces the first -- deliberately permissive, so a caller can
        swap in a custom compiler for one knowledge type (e.g. a
        richer, hand-tuned ``AlgorithmCompiler``) without needing to
        fork this whole registry.
        """
        self._compilers[item_type] = compiler

    def compiler_for(self, item: KnowledgeItem) -> Compiler:
        """The registered compiler for ``item``'s exact type, or the
        nearest registered ancestor's -- the same MRO walk
        ``handbook.core.folders.resolve_folder`` uses, so a future
        ``KnowledgeItem`` subclass (e.g. a specialized ``Problem``
        subtype) is compiled correctly without a new registration.

        Raises:
            UnsupportedKnowledgeTypeError: if neither ``type(item)`` nor
                any of its ancestors has a registered compiler.
        """
        for klass in type(item).__mro__:
            compiler = self._compilers.get(klass)
            if compiler is not None:
                return compiler
        raise UnsupportedKnowledgeTypeError(
            f"No compiler registered for type {type(item).__name__!r}. "
            "Register one via CompilerRegistry.register(), or extend "
            "default_registry() in handbook.learning.compiler.registry."
        )

    def compile(self, item: KnowledgeItem, context: CompilationContext) -> CompilationResult:
        """Convenience wrapper: ``compiler_for(item).compile(item, context)``."""
        return self.compiler_for(item).compile(item, context)


def default_registry() -> CompilerRegistry:
    """A fresh :class:`CompilerRegistry` with every compiler this chunk
    implements pre-registered: ``Algorithm``, ``Problem``, ``Pattern``,
    ``Mistake``, ``Contest``.

    ``Topic`` (see ``handbook.models.topic.Topic``) is deliberately not
    registered -- it wasn't part of this chunk's brief, and a "hub"
    knowledge type that groups other items is a meaningfully different
    compilation problem (it would need to *aggregate* its children's
    content, not just project its own fields) worth its own chunk
    rather than a rushed sixth compiler here. Compiling a ``Topic``
    raises :class:`~handbook.learning.compiler.exceptions.
    UnsupportedKnowledgeTypeError` until then -- see
    ``docs/ARCHITECTURE_NOTES_COMPILER.md``.

    A fresh instance every call, not a shared module-level singleton --
    the same choice ``handbook.handbook.Handbook.__init__`` makes for
    its default ``MarkdownRenderer()``, so nothing here is silently
    shared mutable state across unrelated callers/tests.
    """
    registry = CompilerRegistry()
    registry.register(AlgorithmCompiler.item_type, AlgorithmCompiler())
    registry.register(ProblemCompiler.item_type, ProblemCompiler())
    registry.register(PatternCompiler.item_type, PatternCompiler())
    registry.register(MistakeCompiler.item_type, MistakeCompiler())
    registry.register(ContestCompiler.item_type, ContestCompiler())
    return registry
