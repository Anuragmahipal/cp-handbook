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

from dataclasses import dataclass, field

from handbook.evolution.log import EvolutionLog
from handbook.graph import KnowledgeGraph
from handbook.models.base import KnowledgeItem


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
        evolution: This vault's learning history, if the caller has
            one -- ``None`` for any compilation that doesn't (e.g. the
            golden-snapshot and examples-comparison tests, which build
            a ``CompilationContext`` directly). Sections built from it
            are always optional and always omitted when this is
            ``None``, the same "never padded" rule every other
            optional section already follows -- so adding this field
            changes nothing for any existing caller that doesn't pass
            it.
        items_by_id: A lookup back to full ``KnowledgeItem`` objects by
            id, alongside ``graph`` -- needed only by sections that
            compute statistics over a *backlinked item's own fields*
            (e.g. ``AlgorithmCompiler``'s rating histogram needs each
            related ``Problem``'s ``rating``), since ``graph``'s own
            ``Node``s deliberately carry no such data (see
            ``handbook.graph.node``). ``None``/empty wherever nothing
            needs it -- same "always optional" rule as ``evolution``.
    """

    graph: KnowledgeGraph
    evolution: EvolutionLog | None = None
    items_by_id: dict[str, KnowledgeItem] = field(default_factory=dict)
