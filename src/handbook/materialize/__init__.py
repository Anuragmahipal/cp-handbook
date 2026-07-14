"""Knowledge Materialization: turns bare string references on Problems
(algorithm/pattern/mistake tags, contest ids) into first-class,
persisted ``KnowledgeItem`` notes with a real page of their own.

See :mod:`handbook.materialize.engine` for the design rationale.
"""

from __future__ import annotations

from handbook.materialize.engine import (
    MaterializationEngine,
    MaterializationReport,
    MaterializedItem,
)
from handbook.materialize.state import MaterializeState

__all__ = [
    "MaterializationEngine",
    "MaterializationReport",
    "MaterializedItem",
    "MaterializeState",
]
