"""Round-trip serialization tests: dump_page(compile(item)) -> load_page(...)
must reproduce the exact same ``Page``, for every compiler this chunk
implements. Exercises ``handbook.learning.serialization`` (schema-
version-gated dump/load) against real compiler output, not just the
hand-authored example fixtures the LIR's own test suite already covers.
"""

from __future__ import annotations

import pytest

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.learning.serialization import dump_page, load_page
from handbook.models import Algorithm, Contest, Mistake, Pattern, Platform, Problem


def _rich_items() -> list:
    algo = Algorithm(
        title="Segment Tree",
        category="Data Structure",
        intuition="Binary tree over ranges.",
        implementation="build(1, 0, n - 1);",
        time_complexity="O(log n)",
        space_complexity="O(n)",
        pitfalls=["lazy propagation bugs"],
        related_problems=["Range Sum Query"],
        prerequisites=["Recursion"],
    )
    pattern = Pattern(
        title="Two Pointers",
        description="Move two indices toward each other.",
        recognition_cues=["sorted array", "pair target"],
        related_algorithms=["Segment Tree"],
        example_problems=["Range Sum Query"],
    )
    mistake = Mistake(
        title="Lazy Propagation Bug",
        cause="Forgot to push down before recursing.",
        prevention="Always push_down() before touching children.",
        related_algorithms=["Segment Tree"],
    )
    problem = Problem(
        title="Range Sum Query",
        platform=Platform.CODEFORCES,
        contest="1",
        index="A",
        rating=1700,
        algorithms=["Segment Tree"],
        patterns=["Two Pointers"],
        mistakes=["Lazy Propagation Bug"],
        attempts=2,
    )
    contest = Contest(
        title="Educational Round",
        platform=Platform.CODEFORCES,
        problems=["Range Sum Query"],
        takeaways=["Read the constraints twice"],
        rank=800,
        rating_change=12,
    )
    return [algo, pattern, mistake, problem, contest]


@pytest.mark.parametrize("index", range(5))
def test_compiled_page_round_trips_through_json(index: int):
    items = _rich_items()
    graph = GraphBuilder(items).build()
    compiler = KnowledgeCompiler(graph)
    item = items[index]

    result = compiler.compile(item)
    dumped = dump_page(result.page)
    loaded = load_page(dumped)

    assert loaded == result.page


def test_round_trip_preserves_memory_anchors_and_review_cues():
    items = _rich_items()
    graph = GraphBuilder(items).build()
    compiler = KnowledgeCompiler(graph)

    for item in items:
        result = compiler.compile(item)
        loaded = load_page(dump_page(result.page))
        original_anchors = [a.id for s in result.page.sections for a in s.memory_anchors]
        loaded_anchors = [a.id for s in loaded.sections for a in s.memory_anchors]
        assert original_anchors == loaded_anchors


def test_round_trip_of_sparse_items_with_no_content():
    items = [
        Algorithm(title="Bare"),
        Pattern(title="Bare"),
        Mistake(title="Bare"),
        Problem(title="Bare", platform=Platform.CODEFORCES, contest="1", index="A"),
        Contest(title="Bare", platform=Platform.CODEFORCES),
    ]
    graph = GraphBuilder(items).build()
    compiler = KnowledgeCompiler(graph)

    for item in items:
        result = compiler.compile(item)
        loaded = load_page(dump_page(result.page))
        assert loaded == result.page
