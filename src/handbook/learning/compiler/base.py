"""``Compiler``: the interface every concrete per-kind compiler implements.

One method, ``compile``, mirroring the shape ``handbook.core.renderer.
Renderer`` already established for the storage engine
(``render(item) -> str``) -- here it's ``compile(item, context) ->
CompilationResult``, one ``KnowledgeItem`` subtype in, one
``CompilationResult`` out. Keeping this interface this small is what
lets :class:`~handbook.learning.compiler.registry.CompilerRegistry`
dispatch on it generically, the same way ``handbook.core.folders``
dispatches ``Renderer``-agnostic storage across every knowledge type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Generic, TypeVar

from handbook.learning.compiler.context import CompilationContext
from handbook.learning.compiler.result import CompilationResult
from handbook.models.base import KnowledgeItem

ItemT = TypeVar("ItemT", bound=KnowledgeItem)


class Compiler(ABC, Generic[ItemT]):
    """Base class for every ``KnowledgeItem`` subtype's compiler.

    A concrete subclass sets :attr:`item_type` to the exact
    ``KnowledgeItem`` subclass it handles (used by
    :class:`~handbook.learning.compiler.registry.CompilerRegistry` for
    MRO-based dispatch, the same convention
    ``handbook.core.folders._FOLDER_MAP`` already uses) and implements
    :meth:`compile`.
    """

    item_type: ClassVar[type[KnowledgeItem]]

    @abstractmethod
    def compile(self, item: ItemT, context: CompilationContext) -> CompilationResult:
        """Compile one ``item`` into a renderer-independent ``Page``,
        wrapped in a :class:`~handbook.learning.compiler.result.
        CompilationResult` alongside any warnings about content this
        compilation could not populate.

        Never raises for a sparse item: every field this method reads
        is optional in the domain model, and a section is simply
        omitted -- with a corresponding warning -- when its backing
        field is empty. The only errors a caller should expect to
        catch are ``pydantic.ValidationError`` (a genuine bug in this
        compiler producing invalid LIR) or a graph lookup failure
        surfaced by :mod:`handbook.learning.compiler.helpers` -- both
        of which indicate a defect in the compiler itself, not a
        legitimate "this note isn't filled in yet" state.
        """
        raise NotImplementedError
