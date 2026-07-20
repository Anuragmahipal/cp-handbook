"""Pure, deterministic statistics -- no AI, no invented numbers.

Every function here takes data that already exists (a graph, a list of
``Problem``s, an :class:`~handbook.evolution.log.EvolutionLog`) and
returns a plain, explainable number or list. Nothing in this module
calls out to a model, guesses at intent, or interpolates missing data.
Where a statistic is inherently an approximation (``learning_velocity``,
``mastery_for_count`` in :mod:`handbook.evolution.engine`), the
approximation is a fixed, documented formula, not a fuzzy one -- run it
twice on the same data and it produces the same answer, which is the
whole point of "No AI. Only deterministic evolution." (this chunk's own
words).

Split out from :mod:`handbook.evolution.engine` on purpose: the engine
decides *when to record history* (and must not be called twice with
the same effect -- see its module docstring); everything in this
module is a read-only projection over data that already exists and can
be called as many times as a renderer likes with no side effects at
all. Reused by both ``AlgorithmCompiler`` (per-item stats, Part 2) and
``handbook.sync.notebook_site`` (vault-wide stats, Part 3).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from handbook.graph import KnowledgeGraph
from handbook.models import Problem
from handbook.models.base import KnowledgeItem

_RATING_BUCKET_WIDTH = 200
_RATING_BUCKET_FLOOR = 800
_RATING_BUCKET_CEILING = 2000
_RECENT_ACTIVITY_LIMIT = 5
_VELOCITY_WINDOW = timedelta(days=14)
_STREAK_GAP_TOLERANCE = timedelta(days=1)


def _problem_solve_time(problem: Problem) -> datetime | None:
    """The canonical timestamp for when a problem was solved.

    Uses ``solved_at`` (the first AC submission time) when available,
    falling back to ``created_at`` for backward compatibility with
    Problems that don't have submission history.
    """
    if hasattr(problem, "solved_at") and problem.solved_at is not None:
        return problem.solved_at
    return problem.created_at


def backlink_problems(
    graph: KnowledgeGraph, item_id: str, field_name: str, items_by_id: dict[str, KnowledgeItem]
) -> list[Problem]:
    """Every ``Problem`` that references ``item_id`` via ``field_name``
    (``"algorithms"``/``"patterns"``/``"mistakes"``), resolved from the
    graph's edges back to the real ``Problem`` objects -- the graph
    itself only carries lightweight ``Node``s (id/title/kind, no
    timestamps or ratings; see ``handbook.graph.node``), so anything
    needing a Problem's own fields has to look it back up by id.
    """
    if graph.get(item_id) is None:
        return []
    provenance = f"field:{field_name}"
    problems: list[Problem] = []
    for edge, node in graph.related(item_id, direction="in"):
        if edge.provenance != provenance:
            continue
        item = items_by_id.get(node.id)
        if isinstance(item, Problem):
            problems.append(item)
    return problems


@dataclass(frozen=True, slots=True)
class RatingBucket:
    label: str
    count: int


@dataclass(frozen=True, slots=True)
class AlgorithmEvolutionStats:
    """Everything Part 2 asks an Algorithm page to track, computed
    fresh from the current graph + vault -- never stored, so it is
    always exactly as current as the graph it was built from (same
    "compute live, don't cache" choice ``handbook.sync.notebook_site``
    already makes for dashboard backlink counts).
    """

    total_solves: int
    first_solve: datetime | None
    latest_solve: datetime | None
    solve_frequency_per_week: float | None
    rating_histogram: list[RatingBucket]
    recent_activity: list[tuple[str, datetime]]
    difficulty_progression: list[tuple[str, datetime, int | None]]
    learning_velocity_per_two_weeks: int


def algorithm_evolution_stats(
    graph: KnowledgeGraph,
    item_id: str,
    field_name: str,
    items_by_id: dict[str, KnowledgeItem],
) -> AlgorithmEvolutionStats:
    problems = sorted(
        backlink_problems(graph, item_id, field_name, items_by_id),
        key=_problem_solve_time,
    )
    total = len(problems)
    first_solve = _problem_solve_time(problems[0]) if problems else None
    latest_solve = _problem_solve_time(problems[-1]) if problems else None

    frequency = None
    if total >= 2 and first_solve is not None and latest_solve is not None:
        span_weeks = max((latest_solve - first_solve) / timedelta(weeks=1), 1 / 7)
        frequency = round(total / span_weeks, 2)

    histogram = _rating_histogram(problems)
    recent = [(p.title, _problem_solve_time(p)) for p in problems[-_RECENT_ACTIVITY_LIMIT:][::-1]]
    progression = [(p.title, _problem_solve_time(p), p.rating) for p in problems]
    velocity = _learning_velocity(problems)

    return AlgorithmEvolutionStats(
        total_solves=total,
        first_solve=first_solve,
        latest_solve=latest_solve,
        solve_frequency_per_week=frequency,
        rating_histogram=histogram,
        recent_activity=recent,
        difficulty_progression=progression,
        learning_velocity_per_two_weeks=velocity,
    )


def _rating_histogram(problems: Sequence[Problem]) -> list[RatingBucket]:
    counts: Counter[str] = Counter()
    for problem in problems:
        counts[_bucket_label(problem.rating)] += 1
    ordered_labels = _bucket_labels()
    return [RatingBucket(label=label, count=counts.get(label, 0)) for label in ordered_labels if counts.get(label, 0) > 0]


def _bucket_labels() -> list[str]:
    labels = []
    floor = _RATING_BUCKET_FLOOR
    while floor < _RATING_BUCKET_CEILING:
        labels.append(f"{floor}-{floor + _RATING_BUCKET_WIDTH - 1}")
        floor += _RATING_BUCKET_WIDTH
    labels.append(f"{_RATING_BUCKET_CEILING}+")
    labels.append("unrated")
    return labels


def _bucket_label(rating: int | None) -> str:
    if rating is None:
        return "unrated"
    if rating >= _RATING_BUCKET_CEILING:
        return f"{_RATING_BUCKET_CEILING}+"
    floor = _RATING_BUCKET_FLOOR + (
        (max(rating, _RATING_BUCKET_FLOOR) - _RATING_BUCKET_FLOOR) // _RATING_BUCKET_WIDTH
    ) * _RATING_BUCKET_WIDTH
    return f"{floor}-{floor + _RATING_BUCKET_WIDTH - 1}"


def _learning_velocity(problems: Sequence[Problem]) -> int:
    """How many of this algorithm's solves landed in the 14 days
    ending at its own most recent solve -- deliberately anchored to the
    vault's own latest activity for that item, not wall-clock
    ``datetime.now()``, so this stays deterministic in tests and stays
    meaningful for a vault that isn't synced every single day (see
    ``docs/ARCHITECTURE_NOTES_EVOLUTION.md``).
    """
    if not problems:
        return 0
    reference = _problem_solve_time(problems[-1])
    if reference is None:
        return 0
    window_start = reference - _VELOCITY_WINDOW
    return sum(
        1 for p in problems
        if (t := _problem_solve_time(p)) is not None and window_start <= t <= reference
    )


@dataclass(frozen=True, slots=True)
class PersonalStatistics:
    """Vault-wide learning metrics -- Part 3. Anchored to the latest
    solve in the vault (not wall-clock time), for the same reason
    :func:`_learning_velocity` above is."""

    average_rating: float | None
    rating_growth: float | None
    algorithms_learned: int
    weekly_solves: int
    monthly_solves: int
    topic_distribution: list[tuple[str, int]]
    current_streak_days: int
    longest_streak_days: int
    knowledge_growth_events: int


def personal_statistics(
    problems: Sequence[Problem],
    algorithm_count: int,
    knowledge_growth_events: int,
) -> PersonalStatistics:
    # Only count solved problems, sorted by solve time
    solved = sorted(
        (p for p in problems if getattr(p, "solved", True)),
        key=_problem_solve_time,
    )
    rated = [p for p in solved if p.rating is not None]

    average_rating = round(sum(p.rating for p in rated) / len(rated), 1) if rated else None
    rating_growth = _rating_growth(rated)

    reference = _problem_solve_time(solved[-1]) if solved else None
    weekly = _solves_in_window(solved, reference, timedelta(days=7))
    monthly = _solves_in_window(solved, reference, timedelta(days=30))

    topic_counts: Counter[str] = Counter()
    for problem in solved:
        for relation in problem.algorithms:
            topic_counts[relation.target] += 1
    topic_distribution = topic_counts.most_common()

    current_streak, longest_streak = _solve_streaks(solved)

    return PersonalStatistics(
        average_rating=average_rating,
        rating_growth=rating_growth,
        algorithms_learned=algorithm_count,
        weekly_solves=weekly,
        monthly_solves=monthly,
        topic_distribution=topic_distribution,
        current_streak_days=current_streak,
        longest_streak_days=longest_streak,
        knowledge_growth_events=knowledge_growth_events,
    )


def _rating_growth(rated: Sequence[Problem]) -> float | None:
    """Mean rating of the second half of (chronologically sorted) solves
    minus the mean rating of the first half -- a simple, honest trend
    indicator, not a regression fit. Needs at least 2 rated solves;
    with fewer than 4 the "halves" are just the earliest vs the latest
    solve.
    """
    if len(rated) < 2:
        return None
    midpoint = len(rated) // 2
    first_half = rated[:midpoint] if midpoint else rated[:1]
    second_half = rated[midpoint:] if midpoint else rated[1:]
    first_mean = sum(p.rating for p in first_half) / len(first_half)
    second_mean = sum(p.rating for p in second_half) / len(second_half)
    return round(second_mean - first_mean, 1)


def _solves_in_window(
    solved: Sequence[Problem], reference: datetime | None, window: timedelta
) -> int:
    if reference is None:
        return 0
    start = reference - window
    return sum(
        1 for p in solved
        if (t := _problem_solve_time(p)) is not None and start <= t <= reference
    )


def _solve_streaks(solved: Sequence[Problem]) -> tuple[int, int]:
    """Consecutive-day solve streaks, from each problem's own solve
    date (``solved_at.date()``). ``current_streak_days`` is the streak
    ending on the *last* day anything was solved (not necessarily
    today's wall-clock date -- see the module docstring on why this
    module anchors to the vault's own activity, not real time).
    """
    if not solved:
        return 0, 0
    days = sorted({
        t.date()
        for p in solved
        if (t := _problem_solve_time(p)) is not None
    })
    if not days:
        return 0, 0
    longest = 1
    current = 1
    for previous_day, day in zip(days, days[1:]):
        if (day - previous_day) <= _STREAK_GAP_TOLERANCE:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
    return current, longest
