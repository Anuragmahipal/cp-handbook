"""Storage compatibility tests (deliverable #7 / Definition of Done).

The public storage API (`Handbook.store`) must work for every knowledge
type without any changes to its signature -- the whole point of the
Renderer/StorageEngine split from Chunk 1. These tests exercise exactly
the code sample from the Chunk 2 spec's "Definition of Done" section.
"""

from __future__ import annotations

import pytest

from handbook import Handbook
from handbook.models import Algorithm, Contest, Mistake, Pattern, Problem, Topic


def test_definition_of_done_code_sample(hb: Handbook):
    """Verbatim scenario from the spec: construct one of each type and
    store all of them through the existing public API."""
    problem = Problem(title="Two Sum", platform="LeetCode", contest="Easy", index="1")
    algorithm = Algorithm(title="Hash Map")
    pattern = Pattern(title="Two Pointers")
    mistake = Mistake(title="Off by one")

    hb.store(problem)
    hb.store(algorithm)
    hb.store(pattern)
    hb.store(mistake)

    # Concretely: each item landed in its resolved folder as a .md file.
    assert (hb.root / "Problems" / "two-sum.md").exists()
    assert (hb.root / "Algorithms" / "hash-map.md").exists()
    assert (hb.root / "Patterns" / "two-pointers.md").exists()
    assert (hb.root / "Mistakes" / "off-by-one.md").exists()


def test_contest_and_topic_also_store_through_the_same_api(hb: Handbook):
    """Contest and Topic are new in Chunk 2 and must work identically --
    no special-casing required in Handbook or StorageEngine."""
    contest = Contest(title="Educational Round 100", platform="Codeforces")
    topic = Topic(title="Graph Theory")

    hb.store(contest)
    hb.store(topic)

    assert (hb.root / "Contests" / "educational-round-100.md").exists()
    assert (hb.root / "Topics" / "graph-theory.md").exists()


@pytest.mark.parametrize(
    "item_factory",
    [
        lambda: Algorithm(title="Segment Tree"),
        lambda: Problem(
            title="3Sum", platform="LeetCode", contest="Medium", index="15"
        ),
        lambda: Pattern(title="Sliding Window"),
        lambda: Mistake(title="Integer overflow"),
        lambda: Contest(title="Div 2 Round 999", platform="CF"),
        lambda: Topic(title="Number Theory"),
    ],
    ids=["Algorithm", "Problem", "Pattern", "Mistake", "Contest", "Topic"],
)
def test_every_knowledge_type_stores_and_the_file_contains_its_title(
    hb: Handbook, item_factory
):
    item = item_factory()

    hb.store(item)

    matches = list(hb.root.rglob(f"{item.slug}.md"))
    assert len(matches) == 1
    content = matches[0].read_text(encoding="utf-8")
    assert item.title in content


def test_rich_metadata_survives_the_full_store_and_read_cycle(hb: Handbook):
    """Not just that the file exists -- that the structured metadata we
    designed this whole chunk around actually shows up in the rendered
    output, not just plain scalar fields."""
    problem = Problem(
        title="Longest Increasing Subsequence",
        platform="cf",
        contest="Div 2",
        index="D",
        rating=1800,
        algorithms=["Binary Search", "Patience Sorting"],
        patterns=["Dynamic Programming"],
    )

    hb.store(problem)

    content = (hb.root / "Problems" / "longest-increasing-subsequence.md").read_text(
        encoding="utf-8"
    )
    assert "Binary Search" in content
    assert "Patience Sorting" in content
    assert "Dynamic Programming" in content
    # canonical platform name, not the "cf" shorthand that was passed in
    assert "Codeforces" in content
