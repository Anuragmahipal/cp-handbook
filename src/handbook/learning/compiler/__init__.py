"""The Knowledge -> LIR compiler: the bridge between the CP domain model
(``handbook.models``) and the Learning Intermediate Representation
(``handbook.learning``).

::

    from handbook.graph import GraphBuilder
    from handbook.learning.compiler import KnowledgeCompiler
    from handbook.renderers.notebook import NotebookRenderer

    graph = GraphBuilder(all_known_items).build()
    compiler = KnowledgeCompiler(graph)

    result = compiler.compile(some_algorithm)   # -> CompilationResult
    html = NotebookRenderer().render(result.page)  # -> RenderResult

Every other layer this package touches is complete and untouched by
this chunk: ``handbook.models`` (Chunk 2), ``handbook.graph`` (Chunk
4A), ``handbook.learning`` (the LIR chunk), and
``handbook.renderers.notebook`` (the notebook renderer chunk) are all
consumed exactly as they already exist, never modified, never
redesigned -- this package's only job is to connect them. See
``docs/ARCHITECTURE_NOTES_COMPILER.md`` for the full design rationale.

Module map
----------
``exceptions``          -- ``CompilerError``, ``UnsupportedKnowledgeTypeError``.
``context``              -- ``CompilationContext``: what every compiler
                            needs beyond the item itself (currently just
                            the shared ``KnowledgeGraph``).
``result``                -- ``CompilationResult``: the compiled ``Page``
                            plus any warnings about content it couldn't
                            populate.
``helpers``                -- shared, read-only building blocks every
                            concrete compiler is built from: stable id
                            derivation, timestamp propagation, graph-
                            driven "Related X" sections, default
                            ``MemoryAnchor``/``ReviewCue`` wiring.
``base``                    -- ``Compiler``: the one-method interface
                            every concrete compiler implements.
``algorithm`` / ``problem`` /
``pattern`` / ``mistake`` /
``contest``                  -- one concrete ``Compiler`` per knowledge
                            type this chunk covers.
``registry``                  -- ``CompilerRegistry`` /
                            ``default_registry()``: dispatches a
                            ``KnowledgeItem`` to its compiler by type,
                            MRO-aware.
``knowledge_compiler``         -- ``KnowledgeCompiler``: the public
                            entry point, wiring a graph + registry
                            together.
"""

from __future__ import annotations

from handbook.learning.compiler.algorithm import AlgorithmCompiler
from handbook.learning.compiler.base import Compiler
from handbook.learning.compiler.context import CompilationContext
from handbook.learning.compiler.contest import ContestCompiler
from handbook.learning.compiler.exceptions import CompilerError, UnsupportedKnowledgeTypeError
from handbook.learning.compiler.knowledge_compiler import KnowledgeCompiler
from handbook.learning.compiler.mistake import MistakeCompiler
from handbook.learning.compiler.pattern import PatternCompiler
from handbook.learning.compiler.problem import ProblemCompiler
from handbook.learning.compiler.registry import CompilerRegistry, default_registry
from handbook.learning.compiler.result import CompilationResult

__all__ = [
    # facade
    "KnowledgeCompiler",
    "CompilerRegistry",
    "default_registry",
    # per-kind compilers
    "Compiler",
    "AlgorithmCompiler",
    "ProblemCompiler",
    "PatternCompiler",
    "MistakeCompiler",
    "ContestCompiler",
    # context / result
    "CompilationContext",
    "CompilationResult",
    # errors
    "CompilerError",
    "UnsupportedKnowledgeTypeError",
]
