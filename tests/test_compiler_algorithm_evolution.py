"""Tests for AlgorithmCompiler's evolution-derived sections (Part 2 +
Part 4), and that omitting an evolution log reproduces this compiler's
exact pre-evolution behavior.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from handbook.evolution import EvolutionLog, LearningEvolutionEngine
from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.models import Algorithm, Platform, Problem, Relation


def _problem(title: str, when: datetime, **fields) -> Problem:
    fields.setdefault("platform", Platform.CODEFORCES)
    fields.setdefault("contest", "100")
    fields.setdefault("index", "A")
    return Problem(title=title, created_at=when, updated_at=when, **fields)


def _headings(page) -> list[str]:
    return [section.heading.as_plain_text() for section in page.sections]


def test_no_evolution_log_produces_no_evolution_sections():
    algo = Algorithm(title="Binary Search", intuition="halve the search space")
    graph = GraphBuilder([algo]).build()

    result = KnowledgeCompiler(graph).compile(algo)

    headings = _headings(result.page)
    assert "Learning Progress" not in headings
    assert "Rating Histogram" not in headings
    assert "Recent Activity" not in headings
    assert "Learning History" not in headings


def test_evolution_log_with_no_events_for_this_item_produces_no_sections(vault_root: Path):
    algo = Algorithm(title="Binary Search")
    graph = GraphBuilder([algo]).build()
    log = EvolutionLog(vault_root)  # empty -- nothing evolved yet

    result = KnowledgeCompiler(graph, evolution=log).compile(algo)

    assert "Learning Progress" not in _headings(result.page)


def test_evolution_log_with_solves_adds_the_expected_sections(vault_root: Path):
    base = datetime(2026, 1, 1)
    algo = Algorithm(title="Binary Search")
    problems = [
        _problem(f"P{i}", base + timedelta(days=i * 3), algorithms=[Relation(target="Binary Search")])
        for i in range(3)
    ]
    items = problems + [algo]
    graph = GraphBuilder(items).build()
    items_by_id = {item.id: item for item in items}
    log = EvolutionLog(vault_root)
    LearningEvolutionEngine(log).evolve(items, graph)

    result = KnowledgeCompiler(graph, evolution=log, items_by_id=items_by_id).compile(algo)

    headings = _headings(result.page)
    assert "Learning Progress" in headings
    assert "Rating Histogram" in headings  # still shown, with an "unrated" bucket
    assert "Recent Activity" in headings
    assert "Learning History" in headings


def test_learning_history_section_present_on_every_compiler_kind(vault_root: Path):
    """Part 4: every page kind gets a Learning History section once
    there's history for it -- not just Algorithm."""
    from handbook.models import Contest, Mistake, Pattern

    base = datetime(2026, 1, 1)
    problem = _problem("Candies", base)
    algo = Algorithm(title="Binary Search")
    pattern = Pattern(title="Two Pointers")
    mistake = Mistake(title="Off By One")
    contest = Contest(title="100", platform=Platform.CODEFORCES)

    items = [problem, algo, pattern, mistake, contest]
    graph = GraphBuilder(items).build()
    log = EvolutionLog(vault_root)
    LearningEvolutionEngine(log).evolve(items, graph)

    compiler = KnowledgeCompiler(graph, evolution=log, items_by_id={i.id: i for i in items})

    problem_headings = _headings(compiler.compile(problem).page)
    assert "Learning History" in problem_headings


def test_golden_snapshot_compilations_are_unaffected_by_evolution_support():
    """The exact scenario that would break golden-snapshot tests if this
    chunk's changes weren't fully optional: compiling directly via
    KnowledgeCompiler(graph) with no evolution/items_by_id args, exactly
    as tests/test_compiler_golden.py does."""
    algo = Algorithm(title="Binary Search", intuition="halve the search space")
    graph = GraphBuilder([algo]).build()

    result = KnowledgeCompiler(graph).compile(algo)

    assert result.page is not None  # compiles without error, evolution-free
