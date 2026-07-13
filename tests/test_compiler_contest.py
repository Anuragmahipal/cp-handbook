"""Tests for ContestCompiler, independent of every other compiler."""

from __future__ import annotations

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.learning.enums import CalloutKind
from handbook.models import Contest, ContestType, Platform, Problem


def _headings(page) -> list[str]:
    return [s.heading.as_plain_text() for s in page.sections]


def test_minimal_contest_always_gets_an_overview_section():
    contest = Contest(title="Bare Contest", platform=Platform.CODEFORCES)
    graph = GraphBuilder([contest]).build()
    result = KnowledgeCompiler(graph).compile(contest)

    assert _headings(result.page) == ["Overview"]
    assert len(result.page.sections[0].memory_anchors) == 1  # falls back to Overview


def test_overview_mentions_rank_and_rating_change():
    contest = Contest(
        title="Div 2",
        platform=Platform.CODEFORCES,
        contest_type=ContestType.RATED,
        rank=1200,
        rating_change=25,
        performance_rating=1600,
    )
    graph = GraphBuilder([contest]).build()
    result = KnowledgeCompiler(graph).compile(contest)

    text = result.page.sections[0].blocks[0].content.as_plain_text()
    assert "1200" in text
    assert "+25" in text
    assert "1600" in text


def test_negative_rating_change_keeps_its_sign():
    contest = Contest(title="Div 2", platform=Platform.CODEFORCES, rating_change=-14)
    graph = GraphBuilder([contest]).build()
    result = KnowledgeCompiler(graph).compile(contest)

    text = result.page.sections[0].blocks[0].content.as_plain_text()
    assert "-14" in text
    assert "+-14" not in text


def test_takeaways_become_an_insight_callout_and_get_the_anchor():
    contest = Contest(
        title="Div 2",
        platform=Platform.CODEFORCES,
        takeaways=["Read constraints twice", "Don't skip easy problems"],
    )
    graph = GraphBuilder([contest]).build()
    result = KnowledgeCompiler(graph).compile(contest)

    assert _headings(result.page) == ["Overview", "Takeaways"]
    takeaways_section = result.page.sections[1]
    callout = takeaways_section.blocks[0]
    assert callout.kind == CalloutKind.INSIGHT
    assert len(takeaways_section.memory_anchors) == 1
    assert result.page.sections[0].memory_anchors == ()  # anchor moved off Overview


def test_estimated_minutes_comes_from_duration():
    contest = Contest(title="Div 2", platform=Platform.CODEFORCES, duration_minutes=120)
    graph = GraphBuilder([contest]).build()
    result = KnowledgeCompiler(graph).compile(contest)
    assert result.page.metadata.estimated_minutes == 120


def test_problems_section_reflects_graph():
    contest = Contest(
        title="Div 2", platform=Platform.CODEFORCES, problems=["Problem A", "Problem B"]
    )
    problem_a = Problem(
        title="Problem A", platform=Platform.CODEFORCES, contest="1", index="A"
    )
    problem_b = Problem(
        title="Problem B", platform=Platform.CODEFORCES, contest="1", index="B"
    )
    graph = GraphBuilder([contest, problem_a, problem_b]).build()
    result = KnowledgeCompiler(graph).compile(contest)

    section = next(s for s in result.page.sections if s.heading.as_plain_text() == "Problems")
    text = section.blocks[0].content.as_plain_text()
    assert "Problem A" in text
    assert "Problem B" in text
