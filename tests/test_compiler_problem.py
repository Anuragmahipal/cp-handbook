"""Tests for ProblemCompiler, independent of every other compiler."""

from __future__ import annotations

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.learning.enums import CalloutKind
from handbook.models import Algorithm, Difficulty, Mistake, Platform, Problem, ProblemSource


def _headings(page) -> list[str]:
    return [s.heading.as_plain_text() for s in page.sections]


def test_minimal_problem_always_gets_an_overview_section():
    problem = Problem(title="Bare Problem", platform=Platform.CODEFORCES, contest="1", index="A")
    graph = GraphBuilder([problem]).build()
    result = KnowledgeCompiler(graph).compile(problem)

    assert _headings(result.page) == ["Overview"]
    overview = result.page.sections[0]
    assert len(overview.memory_anchors) == 1  # Overview is always present -> always anchored


def test_overview_mentions_platform_contest_index_and_rating():
    problem = Problem(
        title="Watermelon",
        platform=Platform.CODEFORCES,
        contest="4",
        index="A",
        rating=800,
        source=ProblemSource.PRACTICE,
    )
    graph = GraphBuilder([problem]).build()
    result = KnowledgeCompiler(graph).compile(problem)

    text = result.page.sections[0].blocks[0].content.as_plain_text()
    assert "Codeforces" in text
    assert "4" in text
    assert "A" in text
    assert "800" in text
    assert "Practice" in text


def test_difficulty_falls_back_to_rating_when_unset():
    problem = Problem(
        title="P", platform=Platform.CODEFORCES, contest="1", index="A", rating=1900
    )
    graph = GraphBuilder([problem]).build()
    result = KnowledgeCompiler(graph).compile(problem)
    assert result.page.metadata.difficulty == "1900"


def test_difficulty_uses_formal_difficulty_when_set():
    problem = Problem(
        title="P",
        platform=Platform.CODEFORCES,
        contest="1",
        index="A",
        rating=1900,
        difficulty=Difficulty.HARD,
    )
    graph = GraphBuilder([problem]).build()
    result = KnowledgeCompiler(graph).compile(problem)
    assert result.page.metadata.difficulty == "Hard"


def test_estimated_minutes_comes_from_time_spent():
    problem = Problem(
        title="P",
        platform=Platform.CODEFORCES,
        contest="1",
        index="A",
        time_spent_minutes=42,
    )
    graph = GraphBuilder([problem]).build()
    result = KnowledgeCompiler(graph).compile(problem)
    assert result.page.metadata.estimated_minutes == 42


def test_algorithms_and_patterns_get_separate_sections():
    problem = Problem(
        title="P",
        platform=Platform.CODEFORCES,
        contest="1",
        index="A",
        algorithms=["Binary Search"],
        patterns=["Two Pointers"],
    )
    binary_search = Algorithm(title="Binary Search")
    two_pointers = Algorithm(title="Two Pointers")  # kind doesn't matter for resolution
    graph = GraphBuilder([problem, binary_search, two_pointers]).build()
    result = KnowledgeCompiler(graph).compile(problem)

    assert "Algorithms Used" in _headings(result.page)
    assert "Patterns Used" in _headings(result.page)


def test_multiple_attempts_adds_attempt_history_callout():
    problem = Problem(
        title="P", platform=Platform.CODEFORCES, contest="1", index="A", attempts=3
    )
    graph = GraphBuilder([problem]).build()
    result = KnowledgeCompiler(graph).compile(problem)

    mistakes_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Mistakes"
    )
    callout = mistakes_section.blocks[0]
    assert callout.kind == CalloutKind.MISTAKE
    assert "3 attempts before solving" in callout.body[0].content.as_plain_text()


def test_single_attempt_produces_no_attempt_history_callout():
    problem = Problem(
        title="P", platform=Platform.CODEFORCES, contest="1", index="A", attempts=1
    )
    graph = GraphBuilder([problem]).build()
    result = KnowledgeCompiler(graph).compile(problem)

    assert "Mistakes" not in _headings(result.page)


def test_mistakes_section_merges_authored_and_backlinked_relations():
    problem = Problem(
        title="P",
        platform=Platform.CODEFORCES,
        contest="1",
        index="A",
        mistakes=["Authored Mistake"],
        attempts=2,
    )
    authored = Mistake(title="Authored Mistake")
    backlinked = Mistake(title="Backlinked Mistake", related_problems=["P"])
    graph = GraphBuilder([problem, authored, backlinked]).build()
    result = KnowledgeCompiler(graph).compile(problem)

    mistakes_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Mistakes"
    )
    text = " ".join(
        b.content.as_plain_text() if b.block_type == "text" else b.body[0].content.as_plain_text()
        for b in mistakes_section.blocks
    )
    assert "Authored Mistake" in text
    assert "Backlinked Mistake" in text


def test_prerequisites_reflects_graph():
    problem = Problem(
        title="P", platform=Platform.CODEFORCES, contest="1", index="A",
        prerequisites=["Fast IO"],
    )
    fast_io = Algorithm(title="Fast IO")
    graph = GraphBuilder([problem, fast_io]).build()
    result = KnowledgeCompiler(graph).compile(problem)

    assert "Prerequisites" in _headings(result.page)
