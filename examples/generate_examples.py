"""Builds the four example ``Page`` JSON fixtures in this directory.

Run with ``python examples/generate_examples.py`` from the repo root
(with the project installed) to regenerate
``algorithm_page.json``/``problem_page.json``/``mistake_page.json``/
``pattern_page.json``. They are checked in rather than generated at
test time so the notebook renderer's golden tests have a stable,
version-controlled fixture to render against -- see
``tests/test_notebook_golden.py``.

Each page deliberately exercises a different slice of the LIR: the
algorithm page leans on ``DiagramBlock`` (a small weighted graph) and
code annotations; the problem page is intentionally light (most real
problem notes are short); the mistake page shows a ``MemoryAnchor``/
``ReviewCue`` pair with review history already in progress rather than
brand new; the pattern page shows two ``Arrow``s sequenced with
``order`` to represent a two-step walkthrough.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from handbook.learning.blocks import (
    Arrow,
    Callout,
    CodeAnnotation,
    CodeBlock,
    Connection,
    DiagramBlock,
    ElementPosition,
    TextBlock,
    VisualBlock,
)
from handbook.learning.enums import (
    AnchorType,
    CalloutKind,
    DiagramKind,
    ElementRole,
    Emphasis,
    LayoutHint,
    ReviewStatus,
    TextRole,
)
from handbook.learning.page import Page, PageMetadata, Section
from handbook.learning.review import MemoryAnchor, ReviewCue
from handbook.learning.richtext import RichText, Span
from handbook.learning.serialization import dump_page

_HERE = Path(__file__).resolve().parent


def _text(role: TextRole, text: str) -> TextBlock:
    return TextBlock(role=role, content=RichText.plain(text))


def _tip(kind: CalloutKind, title: str, body: str) -> Callout:
    return Callout(
        kind=kind, title=title, body=(TextBlock(content=RichText.plain(body)),)
    )


# ---------------------------------------------------------------- algorithm


def build_algorithm_page() -> Page:
    metadata = PageMetadata(
        title="Dijkstra's Algorithm",
        summary=(
            "Single-source shortest paths on a graph with non-negative "
            "edge weights, by always finalizing the closest unvisited node."
        ),
        tags=["graphs", "shortest-path", "greedy"],
        source_kind="algorithm",
        difficulty="Medium",
        estimated_minutes=25,
    )

    recognition = Section(
        heading=RichText.plain("Recognition"),
        blocks=(
            _text(
                TextRole.INTUITION,
                "Shortest paths, non-negative weights, one source, "
                "possibly many destinations -- that combination is Dijkstra.",
            ),
            _tip(
                CalloutKind.INSIGHT,
                "When it stops applying",
                "The moment an edge weight can be negative, the greedy "
                "argument breaks and you need Bellman-Ford instead.",
            ),
        ),
    )

    core_idea = Section(
        heading=RichText.plain("Core Idea"),
        blocks=(
            _text(
                TextRole.BODY,
                "Repeatedly pop the closest unvisited node from a priority "
                "queue, finalize its distance, and relax every edge out of it.",
            ),
            _tip(
                CalloutKind.DEFINITION,
                "Relaxation",
                "Relaxing edge (u, v, w) means: if dist[u] + w < dist[v], "
                "improve dist[v] and push it back onto the queue.",
            ),
        ),
    )

    complexity = Section(
        heading=RichText.plain("Complexity"),
        blocks=(
            _text(
                TextRole.BODY,
                "O((V + E) log V) with a binary heap -- each edge can "
                "trigger at most one push, and each push costs log V.",
            ),
        ),
    )

    node_a = VisualBlock(
        id="node-a",
        role=ElementRole.STATE,
        label=RichText.plain("A"),
        value="0",
        position=ElementPosition(row=0, col=0),
        emphasis=True,
    )
    node_b = VisualBlock(
        id="node-b",
        role=ElementRole.STATE,
        label=RichText.plain("B"),
        value="4",
        position=ElementPosition(row=0, col=1),
    )
    node_c = VisualBlock(
        id="node-c",
        role=ElementRole.STATE,
        label=RichText.plain("C"),
        value="2",
        position=ElementPosition(row=1, col=0),
    )
    node_d = VisualBlock(
        id="node-d",
        role=ElementRole.STATE,
        label=RichText.plain("D"),
        value="7",
        position=ElementPosition(row=1, col=1),
    )
    diagram = DiagramBlock(
        kind=DiagramKind.GRAPH,
        caption="Relaxing every edge out of the just-finalized node A",
        layout_hint=LayoutHint.FREEFORM,
        elements=(node_a, node_b, node_c, node_d),
        connections=(
            Connection(from_id="node-b", to_id="node-d", label="3", directed=False),
            Connection(from_id="node-c", to_id="node-d", label="5", directed=False),
        ),
        arrows=(
            Arrow(from_id="node-a", to_id="node-b", label="w=4", order=1),
            Arrow(from_id="node-a", to_id="node-c", label="w=2", order=2),
        ),
    )

    code = CodeBlock(
        language="cpp",
        caption="Dijkstra with a binary heap",
        source=(
            "vector<long long> dist(n, INF);\n"
            "priority_queue<pair<long long,int>, vector<pair<long long,int>>, "
            "greater<>> pq;\n"
            "dist[src] = 0;\n"
            "pq.push({0, src});\n"
            "while (!pq.empty()) {\n"
            "    auto [d, u] = pq.top(); pq.pop();\n"
            "    if (d > dist[u]) continue;\n"
            "    for (auto [v, w] : adj[u]) {\n"
            "        if (dist[u] + w < dist[v]) {\n"
            "            dist[v] = dist[u] + w;\n"
            "            pq.push({dist[v], v});\n"
            "        }\n"
            "    }\n"
            "}"
        ),
        highlighted_lines=(7,),
        annotations=(
            CodeAnnotation(
                line=7,
                note="stale queue entry from before a better distance was "
                "found -- skip it instead of re-relaxing",
            ),
        ),
    )
    anchor = MemoryAnchor(
        target_id=code.id,
        prompt=RichText.plain(
            "Why is `if (d > dist[u]) continue;` needed even though we "
            "never delete stale entries from the queue?"
        ),
        anchor_type=AnchorType.QUESTION,
    )
    diagram_section = Section(
        heading=RichText.plain("Diagram"),
        blocks=(diagram,),
    )
    implementation = Section(
        heading=RichText.plain("Implementation"),
        blocks=(code,),
        memory_anchors=(anchor,),
        review_cues=(ReviewCue(anchor_id=anchor.id, status=ReviewStatus.NEW),),
    )

    mistakes = Section(
        heading=RichText.plain("Mistakes"),
        blocks=(
            _tip(
                CalloutKind.MISTAKE,
                "Negative edges",
                "Running Dijkstra on a graph with a negative edge silently "
                "produces a wrong answer instead of crashing -- it will not "
                "look like a bug until you check by hand.",
            ),
        ),
    )

    return Page(
        metadata=metadata,
        sections=(
            recognition,
            core_idea,
            complexity,
            diagram_section,
            implementation,
            mistakes,
        ),
    )


# ------------------------------------------------------------------ problem


def build_problem_page() -> Page:
    metadata = PageMetadata(
        title="CF 4A -- Watermelon",
        summary=(
            "Split a whole watermelon of weight w into two piles, each an "
            "even positive weight."
        ),
        tags=["math", "constructive", "brute-force"],
        source_kind="problem",
        difficulty="800",
        estimated_minutes=5,
    )

    statement = Section(
        heading=RichText.plain("Statement"),
        blocks=(
            _text(
                TextRole.BODY,
                "Given an integer weight w, decide whether it can be split "
                "into two positive integer weights that are both even.",
            ),
        ),
    )

    approach = Section(
        heading=RichText.plain("Approach"),
        blocks=(
            _tip(
                CalloutKind.INSIGHT,
                "Reduce to parity",
                "Any even w >= 4 splits as 2 and (w - 2), both even and "
                "positive. Odd w can never split into two even parts, and "
                "w = 2 only splits as 1 + 1, neither of which is even.",
            ),
        ),
    )

    code = CodeBlock(
        language="cpp",
        source='cout << (w > 2 && w % 2 == 0 ? "YES" : "NO");',
    )
    anchor = MemoryAnchor(
        target_id=code.id,
        prompt=RichText.plain(
            "Why is w = 2 the one even weight that still answers NO?"
        ),
        anchor_type=AnchorType.QUESTION,
    )
    solution = Section(
        heading=RichText.plain("Code"),
        blocks=(code,),
        memory_anchors=(anchor,),
        review_cues=(ReviewCue(anchor_id=anchor.id, status=ReviewStatus.NEW),),
    )

    mistakes = Section(
        heading=RichText.plain("Mistakes"),
        blocks=(
            _tip(
                CalloutKind.MISTAKE,
                "The w = 2 edge case",
                "First submission forgot the w > 2 check and got a wrong "
                "answer on the w = 2 test case specifically.",
            ),
        ),
    )

    return Page(metadata=metadata, sections=(statement, approach, solution, mistakes))


# ------------------------------------------------------------------ mistake


def build_mistake_page() -> Page:
    metadata = PageMetadata(
        title="Off-by-One in Binary Search Bounds",
        summary=(
            "A recurring bug pattern: updating a bound to `mid` instead of "
            "`mid \u00b1 1` and looping forever on a two-element range."
        ),
        tags=["binary-search", "off-by-one", "debugging"],
        source_kind="mistake",
        estimated_minutes=8,
    )

    what_happened = Section(
        heading=RichText.plain("What Happened"),
        blocks=(
            _text(
                TextRole.BODY,
                "Submission timed out instead of failing outright -- the "
                "usual signature of an infinite loop rather than wrong logic.",
            ),
        ),
    )

    root_cause = Section(
        heading=RichText.plain("Root Cause"),
        blocks=(
            _tip(
                CalloutKind.PITFALL,
                "hi = mid vs. hi = mid - 1",
                "When check(mid) is False, hi must become mid - 1, not mid "
                "-- otherwise a two-element range [lo, lo+1] with mid = lo "
                "never shrinks and the loop never terminates.",
            ),
        ),
    )

    prevention_anchor = MemoryAnchor(
        target_id="prevention-section",
        prompt=RichText.plain(
            "What's the one invariant that must strictly shrink every "
            "iteration of a binary search loop?"
        ),
        anchor_type=AnchorType.QUESTION,
    )
    prevention = Section(
        id="prevention-section",
        heading=RichText.plain("Prevention"),
        blocks=(
            _tip(
                CalloutKind.TIP,
                "The two-element check",
                "Before submitting, trace the loop by hand on the smallest "
                "possible range -- lo, hi = 0, 1 -- and confirm it terminates.",
            ),
        ),
        memory_anchors=(prevention_anchor,),
        review_cues=(
            ReviewCue(
                anchor_id=prevention_anchor.id,
                status=ReviewStatus.DUE,
                strength=0.4,
                review_count=2,
                last_reviewed_at=datetime(2026, 6, 20, 9, 0),
                next_due_at=datetime(2026, 7, 10, 9, 0),
            ),
        ),
    )

    related = Section(
        heading=RichText.plain("Related Problems"),
        blocks=(
            TextBlock(
                content=RichText(
                    spans=(
                        Span(text="First seen on "),
                        Span(
                            text="CF 4A",
                            emphasis=(Emphasis.INLINE_CODE,),
                            link_target="cf-4a-watermelon",
                        ),
                        Span(
                            text=", recurred on a binary-search-on-the-answer "
                            "problem."
                        ),
                    )
                )
            ),
        ),
    )

    return Page(
        metadata=metadata,
        sections=(what_happened, root_cause, prevention, related),
    )


# ------------------------------------------------------------------ pattern


def build_pattern_page() -> Page:
    metadata = PageMetadata(
        title="Two Pointers on a Sorted Array",
        summary=(
            "Collapsing an O(n\u00b2) pair search into O(n) by moving two "
            "indices toward each other instead of checking every pair."
        ),
        tags=["two-pointers", "arrays", "sorted"],
        source_kind="pattern",
        difficulty="Easy",
        estimated_minutes=12,
    )

    intuition = Section(
        heading=RichText.plain("Intuition"),
        blocks=(
            _text(
                TextRole.INTUITION,
                "On a sorted array, if the sum at (left, right) is too big, "
                "only shrinking right can help; if it's too small, only "
                "growing left can. That one-directional argument is what "
                "lets both pointers move only forward, ever.",
            ),
        ),
    )

    values = [1, 3, 5, 8, 12, 15]
    cells = tuple(
        VisualBlock(
            id=f"cell-{i}",
            role=ElementRole.VALUE,
            label=RichText.plain(f"a[{i}]"),
            value=str(v),
            position=ElementPosition(row=0, col=i),
        )
        for i, v in enumerate(values)
    )
    left_1 = VisualBlock(
        id="left-1",
        role=ElementRole.POINTER,
        label=RichText.plain("left"),
        position=ElementPosition(row=1, col=0),
        group="pointer",
    )
    right_1 = VisualBlock(
        id="right-1",
        role=ElementRole.POINTER,
        label=RichText.plain("right"),
        position=ElementPosition(row=1, col=5),
        group="pointer",
    )
    left_2 = VisualBlock(
        id="left-2",
        role=ElementRole.POINTER,
        label=RichText.plain("left"),
        position=ElementPosition(row=2, col=1),
        group="pointer",
        emphasis=True,
    )
    right_2 = VisualBlock(
        id="right-2",
        role=ElementRole.POINTER,
        label=RichText.plain("right"),
        position=ElementPosition(row=2, col=5),
        group="pointer",
    )
    diagram = DiagramBlock(
        kind=DiagramKind.ARRAY,
        caption="Target sum 16: a[0] + a[5] = 16 is too... exact, so stop; "
        "a bigger target would move left inward",
        layout_hint=LayoutHint.LINEAR,
        elements=(*cells, left_1, right_1, left_2, right_2),
        arrows=(
            Arrow(
                from_id="left-1",
                to_id="left-2",
                label="sum too small: left++",
                order=1,
            ),
        ),
    )

    code = CodeBlock(
        language="cpp",
        source=(
            "int left = 0, right = n - 1;\n"
            "while (left < right) {\n"
            "    int sum = a[left] + a[right];\n"
            "    if (sum == target) return true;\n"
            "    if (sum < target) left++;\n"
            "    else right--;\n"
            "}\n"
            "return false;"
        ),
    )
    anchor = MemoryAnchor(
        target_id=code.id,
        prompt=RichText.plain(
            "Why is it safe to only ever move one pointer per iteration, "
            "never both?"
        ),
        anchor_type=AnchorType.QUESTION,
    )
    walkthrough = Section(
        heading=RichText.plain("Walkthrough"),
        blocks=(diagram, code),
        memory_anchors=(anchor,),
        review_cues=(ReviewCue(anchor_id=anchor.id, status=ReviewStatus.NEW),),
    )

    mistakes = Section(
        heading=RichText.plain("Common Mistakes"),
        blocks=(
            _tip(
                CalloutKind.MISTAKE,
                "Moving both pointers at once",
                "Advancing left and right in the same iteration can skip "
                "over the one valid pair entirely -- move exactly one "
                "pointer per step.",
            ),
        ),
    )

    return Page(metadata=metadata, sections=(intuition, walkthrough, mistakes))


def main() -> None:
    pages = {
        "algorithm_page.json": build_algorithm_page(),
        "problem_page.json": build_problem_page(),
        "mistake_page.json": build_mistake_page(),
        "pattern_page.json": build_pattern_page(),
    }
    for filename, page in pages.items():
        (_HERE / filename).write_text(dump_page(page) + "\n", encoding="utf-8")
        print(f"wrote {filename}  ({page.metadata.title})")


if __name__ == "__main__":
    main()
