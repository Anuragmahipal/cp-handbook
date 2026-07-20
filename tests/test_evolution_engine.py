"""Tests for handbook.evolution.engine.LearningEvolutionEngine.

Covers this chunk's Part 7 checklist by name:
large syncs, incremental sync, duplicate sync, history consistency,
mastery updates, timeline ordering.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from handbook.evolution.engine import LearningEvolutionEngine, mastery_for_count
from handbook.evolution.log import EvolutionLog
from handbook.graph import GraphBuilder
from handbook.learning.enums import ReviewStatus
from handbook.models import Algorithm, Platform, Problem, Relation


def _problem(title: str, when: datetime, **fields) -> Problem:
    fields.setdefault("platform", Platform.CODEFORCES)
    fields.setdefault("contest", "100")
    fields.setdefault("index", "A")
    return Problem(title=title, created_at=when, updated_at=when, **fields)


def _engine(vault_root: Path) -> tuple[LearningEvolutionEngine, EvolutionLog]:
    log = EvolutionLog(vault_root)
    return LearningEvolutionEngine(log), log


# -- mastery formula -----------------------------------------------------------


def test_mastery_for_count_thresholds():
    assert mastery_for_count(0) == ReviewStatus.NEW
    assert mastery_for_count(1) == ReviewStatus.LEARNING
    assert mastery_for_count(2) == ReviewStatus.LEARNING
    assert mastery_for_count(3) == ReviewStatus.DUE
    assert mastery_for_count(4) == ReviewStatus.DUE
    assert mastery_for_count(5) == ReviewStatus.MASTERED
    assert mastery_for_count(100) == ReviewStatus.MASTERED


# -- solved events ---------------------------------------------------------


def test_solving_a_problem_records_a_learning_event(vault_root: Path):
    engine, log = _engine(vault_root)
    problem = _problem("Candies", datetime(2026, 1, 1))
    graph = GraphBuilder([problem]).build()

    report = engine.evolve([problem], graph)

    assert len(report.learning_events) == 1
    assert report.learning_events[0].item_id == problem.id
    assert "Solved" in report.learning_events[0].summary


def test_unsolved_problem_records_an_attempted_event(vault_root: Path):
    engine, log = _engine(vault_root)
    problem = _problem("Candies", datetime(2026, 1, 1), solved=False)
    graph = GraphBuilder([problem]).build()

    report = engine.evolve([problem], graph)

    assert "Attempted" in report.learning_events[0].summary


# -- duplicate sync: Part 7 -------------------------------------------------


def test_duplicate_sync_does_not_duplicate_history(vault_root: Path):
    engine, log = _engine(vault_root)
    problem = _problem("Candies", datetime(2026, 1, 1))
    graph = GraphBuilder([problem]).build()

    first = engine.evolve([problem], graph)
    second = engine.evolve([problem], graph)

    assert len(first.learning_events) == 1
    assert second.is_empty
    assert len(log.events()) == 1


# -- incremental sync: Part 7 ------------------------------------------------


def test_incremental_sync_appends_only_the_new_events(vault_root: Path):
    engine, log = _engine(vault_root)
    p1 = _problem("Candies", datetime(2026, 1, 1))
    graph1 = GraphBuilder([p1]).build()
    engine.evolve([p1], graph1)

    p2 = _problem("Ropes", datetime(2026, 1, 5))
    graph2 = GraphBuilder([p1, p2]).build()
    report2 = engine.evolve([p1, p2], graph2)

    assert len(report2.learning_events) == 1
    assert report2.learning_events[0].item_id == p2.id
    assert len(log.events()) == 2  # p1's event from the first run is still there


# -- history consistency: Part 7 --------------------------------------------


def test_history_consistency_across_many_incremental_syncs(vault_root: Path):
    """Sync one new problem at a time, 10 times -- verify nothing already
    recorded is ever lost or altered."""
    engine, log = _engine(vault_root)
    problems: list[Problem] = []
    for i in range(10):
        problems.append(_problem(f"P{i}", datetime(2026, 1, 1) + timedelta(days=i)))
        graph = GraphBuilder(problems).build()
        engine.evolve(problems, graph)

    assert len(log.events()) == 10
    recorded_ids = {event.item_id for event in log.events()}
    assert recorded_ids == {p.id for p in problems}


# -- large syncs: Part 7 -----------------------------------------------------


def test_large_sync_records_an_event_per_problem_and_growth_for_shared_algorithms(
    vault_root: Path,
):
    engine, log = _engine(vault_root)
    base = datetime(2026, 1, 1)
    problems = [
        _problem(f"P{i}", base + timedelta(days=i), algorithms=[Relation(target="Binary Search")])
        for i in range(150)
    ]
    algo = Algorithm(title="Binary Search")
    items = problems + [algo]
    graph = GraphBuilder(items).build()

    report = engine.evolve(items, graph)

    assert len(report.learning_events) == 150
    assert len(report.knowledge_growth) == 1
    assert report.knowledge_growth[0].new_total == 150
    # every mastery threshold crossed in one run still only records the
    # *final* status reached, not one event per intermediate threshold
    assert len(report.mastery_changes) == 1
    assert report.mastery_changes[0].new_status == ReviewStatus.MASTERED


# -- mastery updates: Part 7 -------------------------------------------------


def test_mastery_updates_incrementally_as_solves_accumulate(vault_root: Path):
    engine, log = _engine(vault_root)
    base = datetime(2026, 1, 1)
    algo = Algorithm(title="Binary Search")
    problems: list[Problem] = []
    seen_statuses = []

    for i in range(6):
        problems.append(
            _problem(f"P{i}", base + timedelta(days=i), algorithms=[Relation(target="Binary Search")])
        )
        items = problems + [algo]
        graph = GraphBuilder(items).build()
        report = engine.evolve(items, graph)
        if report.mastery_changes:
            seen_statuses.append(report.mastery_changes[0].new_status)

    assert seen_statuses == [ReviewStatus.LEARNING, ReviewStatus.DUE, ReviewStatus.MASTERED]
    assert log.latest_mastery_for(algo.id) == ReviewStatus.MASTERED


def test_knowledge_growth_recorded_each_time_backlink_count_increases(vault_root: Path):
    engine, log = _engine(vault_root)
    base = datetime(2026, 1, 1)
    algo = Algorithm(title="Binary Search")

    p1 = _problem("P0", base, algorithms=[Relation(target="Binary Search")])
    items = [p1, algo]
    graph = GraphBuilder(items).build()
    report1 = engine.evolve(items, graph)
    assert report1.knowledge_growth[0].previous_total == 0
    assert report1.knowledge_growth[0].new_total == 1

    p2 = _problem("P1", base + timedelta(days=1), algorithms=[Relation(target="Binary Search")])
    items = [p1, p2, algo]
    graph = GraphBuilder(items).build()
    report2 = engine.evolve(items, graph)
    assert report2.knowledge_growth[0].previous_total == 1
    assert report2.knowledge_growth[0].new_total == 2


# -- timeline ordering: Part 7 ------------------------------------------------


def test_timeline_ordering_reflects_when_things_actually_happened(vault_root: Path):
    engine, log = _engine(vault_root)
    early = _problem("Early", datetime(2026, 1, 1))
    late = _problem("Late", datetime(2026, 6, 1))
    # Evolve in reverse chronological order -- the log should still sort
    # by `when`, not by insertion order.
    graph = GraphBuilder([early, late]).build()
    engine.evolve([late, early], graph)

    entries = log.timeline_entries()

    assert [e.item_id for e in entries] == [early.id, late.id]


def test_per_item_timeline_ordering_mixes_solves_growth_and_mastery_correctly(
    vault_root: Path,
):
    engine, log = _engine(vault_root)
    base = datetime(2026, 1, 1)
    algo = Algorithm(title="Binary Search")
    problems: list[Problem] = []
    for i in range(3):
        problems.append(
            _problem(f"P{i}", base + timedelta(days=i), algorithms=[Relation(target="Binary Search")])
        )
        items = problems + [algo]
        graph = GraphBuilder(items).build()
        engine.evolve(items, graph)

    entries = log.timeline_entries(item_id=algo.id)
    assert [e.when for e in entries] == sorted(e.when for e in entries)
    # both growth and mastery events about the algorithm should appear
    labels = " ".join(e.label for e in entries)
    assert "now used by" in labels
    assert "mastery" in labels  # e.g. "mastery new → learning"
