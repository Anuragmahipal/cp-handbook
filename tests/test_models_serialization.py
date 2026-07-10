"""Round-trip serialization tests across every knowledge type.

Each type is constructed with every field populated, dumped to JSON,
and reloaded -- verifying no information is silently lost or corrupted
in the round trip (deliverable #6: "round-trip serialization should
preserve all information").
"""

from __future__ import annotations

import pytest

from handbook.models import (
    Algorithm,
    Contest,
    KnowledgeItem,
    Mistake,
    Pattern,
    Problem,
    Topic,
)

FULLY_POPULATED = [
    Algorithm(
        title="Heavy-Light Decomposition",
        aliases=["HLD"],
        tags=["tree", "advanced"],
        difficulty="Hard",
        sources=["CP-Algorithms"],
        prerequisites=["LCA", "Segment Tree"],
        notes="Decomposes a tree into chains for O(log^2 n) path queries.",
        category="Tree",
        time_complexity="O(log^2 n) per query",
        space_complexity="O(n)",
        intuition="Heavy edges form chains; jump chain by chain.",
        implementation="Two DFS passes: sizes, then chain heads.",
        pitfalls=["forgetting to handle the LCA case"],
        related_problems=["Path Queries"],
    ),
    Problem(
        title="Two Sum",
        platform="LeetCode",
        contest="Easy",
        index="1",
        contest_id="weekly-100",
        url="https://leetcode.com/problems/two-sum/",
        rating=1200,
        source="Practice",
        algorithms=["Hash Map"],
        patterns=["Two Pointers"],
        mistakes=["forgot the empty-input case"],
        solved=True,
        attempts=2,
        time_spent_minutes=15,
    ),
    Pattern(
        title="Two Pointers",
        category="Two Pointers",
        description="Move two indices toward/away from each other.",
        recognition_cues=["sorted array", "pair sum"],
        related_algorithms=["Binary Search"],
        example_problems=["3Sum"],
    ),
    Mistake(
        title="Off by one in binary search",
        category="Off By One",
        cause="Used < instead of <= in the loop condition.",
        prevention="Always test with a 1-element array.",
        occurrences=3,
        related_problems=["Search Insert Position"],
        related_algorithms=["Binary Search"],
    ),
    Contest(
        title="Educational Round 100",
        platform="Codeforces",
        contest_type="Rated",
        duration_minutes=120,
        url="https://codeforces.com/contest/100",
        problems=["A", "B", "C"],
        rank=1500,
        rating_change=25,
        performance_rating=1450,
        takeaways=["read constraints twice"],
    ),
    Topic(
        title="Graph Theory",
        area="Graph",
        description="Algorithms and patterns on graphs.",
        algorithms=["DFS", "BFS"],
        patterns=["Union-Find"],
        key_problems=["Number of Islands"],
    ),
]


@pytest.mark.parametrize("item", FULLY_POPULATED, ids=lambda i: type(i).__name__)
def test_round_trip_via_model_dump_json_mode(item: KnowledgeItem):
    cls = type(item)
    restored = cls.model_validate(item.model_dump(mode="json"))

    assert restored == item


@pytest.mark.parametrize("item", FULLY_POPULATED, ids=lambda i: type(i).__name__)
def test_round_trip_via_json_string(item: KnowledgeItem):
    cls = type(item)
    restored = cls.model_validate_json(item.model_dump_json())

    assert restored == item


@pytest.mark.parametrize("item", FULLY_POPULATED, ids=lambda i: type(i).__name__)
def test_dumped_json_has_no_python_only_types(item: KnowledgeItem):
    """Everything should be JSON-primitive: no raw datetimes, enums, or
    nested model objects left un-dumped."""
    import json

    dumped = item.model_dump(mode="json")
    json.dumps(dumped)  # raises if anything isn't JSON-serializable


@pytest.mark.parametrize("item", FULLY_POPULATED, ids=lambda i: type(i).__name__)
def test_every_type_is_a_knowledge_item(item: KnowledgeItem):
    assert isinstance(item, KnowledgeItem)
    assert item.kind == type(item).KIND
