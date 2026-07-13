"""Example LIR vs. Compiled LIR: a quality comparison, not an equality test.

Per the chunk brief ("Delete NO examples ... instead: add a comparison
test, Example LIR vs Compiled LIR, to verify quality"), ``examples/*.
json`` remain the project's hand-authored demonstration fixtures --
this test does not touch them. What it checks is whether an equivalent
``KnowledgeItem`` (populated with the same underlying facts the fixture
was hand-written from) compiles to a ``Page`` that covers the same
ground.

The two are **not** expected to match section-for-section. The example
fixtures were authored directly against the LIR and contain prose no
domain-model field carries (an algorithm's "when it stops applying"
aside, a pattern's fully worked two-pointer walkthrough diagram, a
problem's actual solution code) -- inventing that prose here would
require exactly the kind of AI-generated content the chunk brief rules
out. So this test asserts two different things per fixture:

* every heading the compiler **should** be able to produce, given the
  domain fields it actually has, is present (a real coverage check --
  this fails if the compiler regresses); and
* every heading the compiler **cannot** produce is named and reasoned
  about explicitly, not silently ignored.

Both the example page and the compiled page are also asserted to
render through ``NotebookRenderer`` without error -- "verify quality"
includes "is this actually usable by the one renderer that exists
today", not just "does it parse".
"""

from __future__ import annotations

from pathlib import Path

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.learning.serialization import load_page
from handbook.models import Algorithm, Mistake, Pattern, Platform, Problem, ProblemSource
from handbook.renderers.notebook import NotebookRenderer

_EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _example_headings(filename: str) -> list[str]:
    page = load_page((_EXAMPLES_DIR / filename).read_text(encoding="utf-8"))
    return [s.heading.as_plain_text() for s in page.sections]


def _compiled_headings(page) -> list[str]:
    return [s.heading.as_plain_text() for s in page.sections]


def _assert_renders(page) -> None:
    result = NotebookRenderer().render(page)
    assert "<html" in result.html
    assert result.html.strip().endswith("</html>")


# ---------------------------------------------------------------- algorithm


def test_algorithm_example_vs_compiled():
    example_headings = _example_headings("algorithm_page.json")
    assert example_headings == [
        "Recognition",
        "Core Idea",
        "Complexity",
        "Diagram",
        "Implementation",
        "Mistakes",
    ]

    algo = Algorithm(
        title="Dijkstra's Algorithm",
        intuition=(
            "Shortest paths, non-negative weights, one source, possibly many "
            "destinations -- that combination is Dijkstra."
        ),
        implementation=(
            "priority_queue<pair<long long,int>, vector<pair<long long,int>>, "
            "greater<>> pq;\ndist[src] = 0;\npq.push({0, src});"
        ),
        time_complexity="O((V + E) log V) with a binary heap",
    )
    negative_edges = Mistake(
        title="Negative edges break Dijkstra",
        cause="A negative edge weight silently produces a wrong answer.",
        related_algorithms=["Dijkstra's Algorithm"],
    )
    graph = GraphBuilder([algo, negative_edges]).build()
    result = KnowledgeCompiler(graph).compile(algo)
    compiled_headings = _compiled_headings(result.page)

    # Coverable from Algorithm's own fields -- must actually appear:
    assert "Complexity" in compiled_headings
    assert "Implementation" in compiled_headings
    assert "Mistakes" in compiled_headings  # graph-driven, not fabricated

    # "Recognition" has no separate domain field from "Core Idea" --
    # Algorithm only has one `intuition` string, so the compiler
    # produces a single "Intuition" section covering the same ground
    # as the fixture's "Recognition" section (not a heading-for-heading
    # match, a content-source match).
    assert "Intuition" in compiled_headings

    # Explicitly NOT expected, and why:
    # - "Core Idea": the fixture splits intuition into two authored
    #   paragraphs across "Recognition" and "Core Idea"; the domain
    #   model has one `intuition` field, not two, so producing a
    #   second section here would mean inventing a split that isn't
    #   in the source data.
    # - "Diagram": no diagram is synthesized from bare metadata (see
    #   AlgorithmCompiler's module docstring / ARCHITECTURE_NOTES) --
    #   only DiagramBlocks a human explicitly authored would appear
    #   here, and Algorithm carries no diagram field at all.
    assert "Core Idea" not in compiled_headings
    assert "Diagram" not in compiled_headings

    _assert_renders(result.page)


# ------------------------------------------------------------------ problem


def test_problem_example_vs_compiled():
    example_headings = _example_headings("problem_page.json")
    assert example_headings == ["Statement", "Approach", "Code", "Mistakes"]

    problem = Problem(
        title="CF 4A -- Watermelon",
        platform=Platform.CODEFORCES,
        contest="4",
        index="A",
        rating=800,
        source=ProblemSource.PRACTICE,
        attempts=2,  # first submission forgot the w > 2 edge case
    )
    graph = GraphBuilder([problem]).build()
    result = KnowledgeCompiler(graph).compile(problem)
    compiled_headings = _compiled_headings(result.page)

    # Coverable: attempt count is real, mechanical data.
    assert "Mistakes" in compiled_headings
    assert "Overview" in compiled_headings  # the compiler's structural-facts section

    # Explicitly NOT expected: "Statement"/"Approach"/"Code" all require
    # prose or source code the Problem domain model has no field for
    # at all (see ProblemCompiler's module docstring) -- that content
    # lives in handbook.sync.revision_note.RevisionNote instead, left
    # for a human to fill in by hand, never fabricated here.
    assert "Statement" not in compiled_headings
    assert "Approach" not in compiled_headings
    assert "Code" not in compiled_headings

    _assert_renders(result.page)


# ------------------------------------------------------------------ pattern


def test_pattern_example_vs_compiled():
    example_headings = _example_headings("pattern_page.json")
    assert example_headings == ["Intuition", "Walkthrough", "Common Mistakes"]

    pattern = Pattern(
        title="Two Pointers on a Sorted Array",
        description=(
            "On a sorted array, if the sum at (left, right) is too big, only "
            "shrinking right can help; if it's too small, only growing left can."
        ),
        recognition_cues=["sorted array", "pair sum target"],
    )
    moved_both = Mistake(
        title="Moved both pointers at once",
        cause="Advancing left and right in the same iteration skipped the pair.",
        related_algorithms=["Two Pointers on a Sorted Array"],
    )
    graph = GraphBuilder([pattern, moved_both]).build()
    result = KnowledgeCompiler(graph).compile(pattern)
    compiled_headings = _compiled_headings(result.page)

    # Exact heading match is possible here:
    assert "Intuition" in compiled_headings
    # The compiler's "Mistakes" section covers the same ground as the
    # fixture's "Common Mistakes" (a naming choice consistent with
    # every other compiler's "Mistakes" heading, rather than one
    # pattern-specific label).
    assert "Mistakes" in compiled_headings

    # Explicitly NOT expected: "Walkthrough" is a fully worked
    # DiagramBlock + CodeBlock demonstration -- Pattern has neither a
    # diagram field nor a code field, only recognition_cues/description,
    # which the compiler already turns into "Intuition"/"Recognition
    # Cues" instead of fabricating a walkthrough that isn't there.
    assert "Walkthrough" not in compiled_headings

    _assert_renders(result.page)


# ------------------------------------------------------------------ mistake


def test_mistake_example_vs_compiled():
    example_headings = _example_headings("mistake_page.json")
    assert example_headings == [
        "What Happened",
        "Root Cause",
        "Prevention",
        "Related Problems",
    ]

    mistake = Mistake(
        title="Off-by-One in Binary Search Bounds",
        cause=(
            "When check(mid) is False, hi must become mid - 1, not mid -- "
            "otherwise a two-element range never shrinks."
        ),
        prevention=(
            "Before submitting, trace the loop by hand on the smallest "
            "possible range and confirm it terminates."
        ),
        related_problems=["CF 4A -- Watermelon"],
    )
    watermelon = Problem(
        title="CF 4A -- Watermelon",
        platform=Platform.CODEFORCES,
        contest="4",
        index="A",
    )
    graph = GraphBuilder([mistake, watermelon]).build()
    result = KnowledgeCompiler(graph).compile(mistake)
    compiled_headings = _compiled_headings(result.page)

    # Mistake's domain fields map onto the fixture's sections one-to-one --
    # this is the one kind where full structural parity is expected.
    assert compiled_headings[:3] == ["What Happened", "Root Cause", "Prevention"]
    assert "Related Problems" in compiled_headings

    _assert_renders(result.page)
