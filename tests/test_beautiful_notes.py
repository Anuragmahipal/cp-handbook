"""Chunk 3 rendering tests: verify the generated Markdown actually has
the structural properties the Beautiful Note System spec asked for --
callouts, collapsible sections, Mermaid diagrams, Dataview blocks,
AI-managed prose markers, and a consistent visual hierarchy -- across
all five in-scope knowledge types.

Two helpers (assert_well_formed_callouts / assert_no_glued_bullets)
are regression guards for a specific class of bug found while building
these templates: Jinja's trim_blocks setting silently swallows the
newline after *any* line ending in a `{% ... %}` tag, even when that
line has real rendered content before the tag. That collapses blank
lines between adjacent callouts and glues bulleted relation items
together. The fix (ternary `{{ }}` expressions instead of trailing
`{% if %}...{% endif %}`, and a `blockquote` filter that preserves a
trailing newline) is now standard across every template -- these tests
make sure it stays that way.
"""

from __future__ import annotations

import re

import pytest

from handbook.models import Algorithm, Contest, Mistake, Pattern, Problem
from handbook.renderers.markdown_renderer import MarkdownRenderer

RENDERER = MarkdownRenderer()


def assert_well_formed_callouts(content: str) -> None:
    """Every Obsidian callout header (`> [!type]`) must be preceded by
    a real blank line, or it silently becomes part of the previous
    callout instead of starting a new one."""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("> [!") and i > 0:
            assert lines[i - 1] == "", (
                f"line {i} starts a callout but isn't preceded by a blank line: "
                f"{lines[i - 1]!r} -> {line!r}"
            )


def assert_no_glued_bullets(content: str) -> None:
    """No two `- **target**` relation bullets should ever end up on the
    same line -- that's the signature of a swallowed newline."""
    for line in content.splitlines():
        assert not re.search(r"\*\*.*-\s*\*\*", line), (
            f"glued bullets on one line: {line!r}"
        )


FULLY_POPULATED = {
    "Algorithm": Algorithm(
        title="Heavy-Light Decomposition",
        aliases=["HLD"],
        category="Tree",
        difficulty="Hard",
        time_complexity="O(log^2 n)",
        space_complexity="O(n)",
        intuition="Chains of heavy edges.",
        implementation="Two DFS passes.",
        pitfalls=["Forgetting the LCA case", "Off-by-one in indices"],
        prerequisites=["LCA", "Segment Tree"],
        related_problems=["Path Queries"],
        sources=["CP-Algorithms"],
        notes="Revisit soon.",
    ),
    "Problem": Problem(
        title="Longest Increasing Subsequence",
        platform="cf",
        contest="Div 2",
        index="D",
        rating=1800,
        algorithms=["Binary Search", "Patience Sorting"],
        patterns=["Dynamic Programming"],
        mistakes=["forgot the empty-input case"],
        notes="Binary search on tails.",
    ),
    "Pattern": Pattern(
        title="Two Pointers",
        category="Two Pointers",
        description="Move two indices toward each other.",
        recognition_cues=["sorted array", "pair sum"],
        related_algorithms=["Binary Search"],
        example_problems=["3Sum"],
    ),
    "Mistake": Mistake(
        title="TLE from recursion",
        category="tle",
        cause="No memoization.",
        prevention="Always memoize.",
        occurrences=3,
        related_problems=["Fibonacci"],
        related_algorithms=["DP"],
    ),
    "Contest": Contest(
        title="Educational Round 100",
        platform="Codeforces",
        start_time="2026-07-01T14:35:00",
        duration_minutes=120,
        problems=["A", "B", "C"],
        rank=1500,
        takeaways=["Read constraints twice"],
        notes="Solid round.",
    ),
}

MINIMAL = {
    "Algorithm": Algorithm(title="Binary Lifting"),
    "Problem": Problem(title="Two Sum", platform="LeetCode", contest="Easy", index="1"),
    "Pattern": Pattern(title="Sliding Window"),
    "Mistake": Mistake(title="Off by one"),
    "Contest": Contest(title="Div 2 Round 999", platform="CF"),
}


# -- structural well-formedness, every type, both populated and empty ----------


@pytest.mark.parametrize("item", FULLY_POPULATED.values(), ids=FULLY_POPULATED.keys())
def test_fully_populated_notes_are_well_formed(item):
    content = RENDERER.render(item)
    assert_well_formed_callouts(content)
    assert_no_glued_bullets(content)


@pytest.mark.parametrize("item", MINIMAL.values(), ids=MINIMAL.keys())
def test_minimal_notes_are_well_formed(item):
    content = RENDERER.render(item)
    assert_well_formed_callouts(content)
    assert_no_glued_bullets(content)


@pytest.mark.parametrize("item", MINIMAL.values(), ids=MINIMAL.keys())
def test_minimal_notes_never_leak_a_bare_python_none(item):
    """Optional fields (rating, start_time, ...) must render a friendly
    placeholder, never the literal string 'None' as a value."""
    content = RENDERER.render(item)
    for bad in ("**Rating:** None", "**Started:** None", "**Link:** None", ": None\n"):
        assert bad not in content


# -- callouts --------------------------------------------------------------------


@pytest.mark.parametrize("item", FULLY_POPULATED.values(), ids=FULLY_POPULATED.keys())
def test_every_type_uses_callouts(item):
    content = RENDERER.render(item)
    assert "> [!" in content


@pytest.mark.parametrize("item", FULLY_POPULATED.values(), ids=FULLY_POPULATED.keys())
def test_every_type_has_collapsible_sections(item):
    """Progressive disclosure: at least one callout defaults collapsed."""
    content = RENDERER.render(item)
    assert re.search(r"> \[!\w+\]-", content), "no collapsed (`]-`) callout found"


@pytest.mark.parametrize("item", FULLY_POPULATED.values(), ids=FULLY_POPULATED.keys())
def test_every_type_has_at_least_one_expanded_primary_callout(item):
    content = RENDERER.render(item)
    assert re.search(r"> \[!\w+\]\+", content), "no expanded (`]+`) callout found"


# -- Mermaid ----------------------------------------------------------------------


def test_algorithm_mermaid_present_when_relations_exist():
    content = RENDERER.render(FULLY_POPULATED["Algorithm"])
    assert "```mermaid" in content
    assert "graph LR" in content
    assert "LCA" in content


def test_algorithm_mermaid_absent_when_no_relations():
    """The mermaid diagram is only worth drawing when there's at least
    one relation -- algorithm.md.j2 guards the call so the diagram
    macro's own internal fallback text is never reached; each relation
    list's own empty-state message covers it instead (progressive
    disclosure: no empty scaffolding for a brand-new item)."""
    content = RENDERER.render(MINIMAL["Algorithm"])
    assert "```mermaid" not in content
    assert "None -- this stands on its own." in content
    assert "No linked problems yet." in content


@pytest.mark.parametrize(
    "item",
    [FULLY_POPULATED[k] for k in ("Problem", "Pattern", "Mistake", "Contest")],
    ids=["Problem", "Pattern", "Mistake", "Contest"],
)
def test_mermaid_present_for_every_type_when_populated(item):
    content = RENDERER.render(item)
    assert "```mermaid" in content
    assert "graph LR" in content


# -- Dataview -----------------------------------------------------------------------


@pytest.mark.parametrize("item", FULLY_POPULATED.values(), ids=FULLY_POPULATED.keys())
def test_every_type_emits_a_dataview_block(item):
    content = RENDERER.render(item)
    assert "```dataview" in content
    assert "this." in content  # queries reference the current file's own fields


# -- AI-managed / editable sections -----------------------------------------------


@pytest.mark.parametrize(
    ("item", "marker"),
    [
        (FULLY_POPULATED["Algorithm"], "intuition"),
        (FULLY_POPULATED["Problem"], "approach"),
        (FULLY_POPULATED["Pattern"], "description"),
        (FULLY_POPULATED["Mistake"], "cause"),
        (FULLY_POPULATED["Contest"], "reflection"),
    ],
    ids=["Algorithm", "Problem", "Pattern", "Mistake", "Contest"],
)
def test_primary_prose_field_is_ai_marked(item, marker):
    content = RENDERER.render(item)
    assert f"<!-- ai:{marker}:start -->" in content
    assert f"<!-- ai:{marker}:end -->" in content


def test_ai_markers_wrap_the_actual_authored_content():
    content = RENDERER.render(FULLY_POPULATED["Algorithm"])
    start = content.index("<!-- ai:intuition:start -->")
    end = content.index("<!-- ai:intuition:end -->")
    assert start < content.index("Chains of heavy edges.") < end


# -- consistent visual hierarchy / shared footer -----------------------------------


@pytest.mark.parametrize("item", FULLY_POPULATED.values(), ids=FULLY_POPULATED.keys())
def test_every_type_ends_with_the_shared_metadata_footer(item):
    content = RENDERER.render(item)
    assert "[!info]- 📋 Metadata" in content
    assert f"**Id:** `{item.id}`" in content
    assert f"**Slug:** `{item.slug}`" in content
    assert f"**Kind:** {item.kind}" in content


@pytest.mark.parametrize("item", FULLY_POPULATED.values(), ids=FULLY_POPULATED.keys())
def test_every_type_opens_with_a_quick_facts_callout(item):
    content = RENDERER.render(item)
    assert "[!tip]+ Quick Facts" in content


@pytest.mark.parametrize("item", FULLY_POPULATED.values(), ids=FULLY_POPULATED.keys())
def test_frontmatter_declares_obsidian_native_aliases(item):
    """`aliases:` in frontmatter is an Obsidian-native key -- populating
    it (not just storing aliases as a plain custom field) is what makes
    alternate names actually work for search/linking in the vault."""
    content = RENDERER.render(item)
    assert content.split("---", 2)[1].strip().startswith("title:")
    assert "aliases:" in content


@pytest.mark.parametrize("item", FULLY_POPULATED.values(), ids=FULLY_POPULATED.keys())
def test_frontmatter_is_the_very_first_thing_in_the_file(item):
    content = RENDERER.render(item)
    assert content.startswith("---\n")


# -- static vs dynamic separation ---------------------------------------------------


def test_editable_sections_are_visually_distinct_from_generated_metadata():
    """The AI-managed markers should only wrap prose fields, never the
    generated, always-fresh metadata footer."""
    content = RENDERER.render(FULLY_POPULATED["Algorithm"])
    footer = content.split("[!info]- 📋 Metadata", 1)[1]
    assert "<!-- ai:" not in footer
