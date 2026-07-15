"""Learning Evolution: turns the notebook from static documentation
into an append-only history of what was learned, when.

See :mod:`handbook.evolution.engine` for how "what changed since last
sync" is detected, :mod:`handbook.evolution.log` for how it's
persisted (append-only, on purpose), and :mod:`handbook.evolution.stats`
for the deterministic statistics built on top of it.
"""

from __future__ import annotations

from handbook.evolution.engine import (
    LearningEvolutionEngine,
    EvolutionReport,
    mastery_for_count,
)
from handbook.evolution.events import (
    EventKind,
    KnowledgeGrowth,
    LearningEvent,
    MasteryChange,
    TimelineEntry,
)
from handbook.evolution.log import EvolutionLog
from handbook.evolution.stats import (
    AlgorithmEvolutionStats,
    PersonalStatistics,
    algorithm_evolution_stats,
    personal_statistics,
)

__all__ = [
    "LearningEvolutionEngine",
    "EvolutionReport",
    "mastery_for_count",
    "EventKind",
    "KnowledgeGrowth",
    "LearningEvent",
    "MasteryChange",
    "TimelineEntry",
    "EvolutionLog",
    "AlgorithmEvolutionStats",
    "PersonalStatistics",
    "algorithm_evolution_stats",
    "personal_statistics",
]
