"""Tests for handbook.evolution.stats."""

from __future__ import annotations

from datetime import datetime, timedelta

from handbook.evolution.stats import algorithm_evolution_stats, personal_statistics
from handbook.graph import GraphBuilder
from handbook.models import Algorithm, Platform, Problem, Relation


def _problem(title: str, when: datetime, rating: int | None = None, **fields) -> Problem:
    fields.setdefault("platform", Platform.CODEFORCES)
    fields.setdefault("contest", "100")
    fields.setdefault("index", "A")
    return Problem(title=title, created_at=when, updated_at=when, rating=rating, **fields)


# -- algorithm_evolution_stats -------------------------------------------------


def test_total_solves_and_first_last_solve():
    base = datetime(2026, 1, 1)
    problems = [
        _problem("P0", base, algorithms=[Relation(target="Binary Search")]),
        _problem("P1", base + timedelta(days=10), algorithms=[Relation(target="Binary Search")]),
    ]
    algo = Algorithm(title="Binary Search")
    items = problems + [algo]
    graph = GraphBuilder(items).build()
    items_by_id = {i.id: i for i in items}

    stats = algorithm_evolution_stats(graph, algo.id, "algorithms", items_by_id)

    assert stats.total_solves == 2
    assert stats.first_solve == base
    assert stats.latest_solve == base + timedelta(days=10)


def test_rating_histogram_buckets_by_200_point_bands():
    base = datetime(2026, 1, 1)
    problems = [
        _problem("P0", base, rating=850, algorithms=[Relation(target="Binary Search")]),
        _problem("P1", base, rating=950, algorithms=[Relation(target="Binary Search")]),
        _problem("P2", base, rating=1250, algorithms=[Relation(target="Binary Search")]),
        _problem("P3", base, rating=None, algorithms=[Relation(target="Binary Search")]),
    ]
    algo = Algorithm(title="Binary Search")
    items = problems + [algo]
    graph = GraphBuilder(items).build()
    items_by_id = {i.id: i for i in items}

    stats = algorithm_evolution_stats(graph, algo.id, "algorithms", items_by_id)

    labels = {b.label: b.count for b in stats.rating_histogram}
    assert labels["800-999"] == 2
    assert labels["1200-1399"] == 1
    assert labels["unrated"] == 1


def test_recent_activity_is_most_recent_first_capped_at_five():
    base = datetime(2026, 1, 1)
    problems = [
        _problem(f"P{i}", base + timedelta(days=i), algorithms=[Relation(target="Binary Search")])
        for i in range(8)
    ]
    algo = Algorithm(title="Binary Search")
    items = problems + [algo]
    graph = GraphBuilder(items).build()
    items_by_id = {i.id: i for i in items}

    stats = algorithm_evolution_stats(graph, algo.id, "algorithms", items_by_id)

    assert len(stats.recent_activity) == 5
    assert stats.recent_activity[0][0] == "P7"  # most recent first


def test_learning_velocity_counts_solves_within_14_days_of_the_latest():
    base = datetime(2026, 1, 1)
    problems = [
        _problem("Old", base, algorithms=[Relation(target="Binary Search")]),
        _problem("Recent1", base + timedelta(days=20), algorithms=[Relation(target="Binary Search")]),
        _problem("Recent2", base + timedelta(days=25), algorithms=[Relation(target="Binary Search")]),
    ]
    algo = Algorithm(title="Binary Search")
    items = problems + [algo]
    graph = GraphBuilder(items).build()
    items_by_id = {i.id: i for i in items}

    stats = algorithm_evolution_stats(graph, algo.id, "algorithms", items_by_id)

    # "Old" (day 0) is outside the 14-day window ending at day 25
    assert stats.learning_velocity_per_two_weeks == 2


def test_stats_for_an_item_with_no_solves_is_all_empty():
    algo = Algorithm(title="Binary Search")
    graph = GraphBuilder([algo]).build()

    stats = algorithm_evolution_stats(graph, algo.id, "algorithms", {algo.id: algo})

    assert stats.total_solves == 0
    assert stats.first_solve is None
    assert stats.solve_frequency_per_week is None
    assert stats.rating_histogram == []


# -- personal_statistics --------------------------------------------------------


def test_average_rating_and_rating_growth():
    base = datetime(2026, 1, 1)
    problems = [
        _problem("P0", base, rating=800),
        _problem("P1", base + timedelta(days=1), rating=900),
        _problem("P2", base + timedelta(days=2), rating=1400),
        _problem("P3", base + timedelta(days=3), rating=1500),
    ]

    stats = personal_statistics(problems, algorithm_count=1, knowledge_growth_events=0)

    assert stats.average_rating == 1150.0
    # second half mean (1450) - first half mean (850) = 600
    assert stats.rating_growth == 600.0


def test_weekly_and_monthly_solve_counts_anchor_to_latest_solve_not_wall_clock():
    base = datetime(2026, 1, 1)
    problems = [
        _problem("Old", base),
        _problem("Recent1", base + timedelta(days=25)),
        _problem("Recent2", base + timedelta(days=27)),
        _problem("Recent3", base + timedelta(days=28)),
    ]

    stats = personal_statistics(problems, algorithm_count=0, knowledge_growth_events=0)

    assert stats.weekly_solves == 3  # within 7 days of day 28
    assert stats.monthly_solves == 4  # all within 30 days of day 28


def test_topic_distribution_counts_algorithm_tags():
    base = datetime(2026, 1, 1)
    problems = [
        _problem("P0", base, algorithms=[Relation(target="Binary Search")]),
        _problem("P1", base, algorithms=[Relation(target="Binary Search")]),
        _problem("P2", base, algorithms=[Relation(target="DP")]),
    ]

    stats = personal_statistics(problems, algorithm_count=2, knowledge_growth_events=0)

    assert stats.topic_distribution[0] == ("Binary Search", 2)


def test_solve_streak_consecutive_days():
    base = datetime(2026, 1, 1)
    problems = [
        _problem("P0", base),
        _problem("P1", base + timedelta(days=1)),
        _problem("P2", base + timedelta(days=2)),
        _problem("P3", base + timedelta(days=10)),  # breaks the streak
    ]

    stats = personal_statistics(problems, algorithm_count=0, knowledge_growth_events=0)

    assert stats.longest_streak_days == 3
    assert stats.current_streak_days == 1  # streak ending on the latest solve day


def test_personal_statistics_on_empty_vault_does_not_crash():
    stats = personal_statistics([], algorithm_count=0, knowledge_growth_events=0)
    assert stats.average_rating is None
    assert stats.rating_growth is None
    assert stats.weekly_solves == 0
    assert stats.current_streak_days == 0
