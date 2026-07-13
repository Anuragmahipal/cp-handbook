"""``CompilationContext``: what every compiler needs, beyond the item itself.

A plain, immutable ``dataclass`` -- not a Pydantic/LIR model -- for the
same reason ``handbook.core.storage.StoragePlan`` is a dataclass rather
than a Pydantic model: this is compiler-internal bookkeeping, never
serialized, never part of the representation ``handbook.learning``
defines. Keeping it a dataclass also makes the boundary visually
obvious in every compiler's signature: ``LIRModel`` in, ``LIRModel``
out, ``CompilationContext`` is neither.
"""

from __future__ import annotations

from dataclasses import dataclass

from handbook.graph import KnowledgeGraph


@dataclass(frozen=True, slots=True)
class CompilationContext:
    """Everything a :class:`~handbook.learning.compiler.base.Compiler`
    needs beyond the single ``KnowledgeItem`` it's compiling.

    Args:
        graph: The knowledge graph to consult for relationships
            (prerequisites, related items, backlinks). Built once
            (typically by :class:`~handbook.graph.GraphBuilder`, over
            *every* known item -- not just the one being compiled) and
            reused across an entire compilation run, so a compiler
            never has to build or duplicate any graph logic itself --
            see :mod:`handbook.learning.compiler.helpers` for the
            handful of read-only queries every compiler shares.
    """

    graph: KnowledgeGraph
