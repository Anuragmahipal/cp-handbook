"""One fully worked :class:`~handbook.learning.page.Page`.

Not a renderer, and not a test in itself -- a living example of what
this representation is actually expressive enough to hold: prose with
semantic roles, a diagram built from typed elements and edges (an
array, two pointers, and the moves between them), an annotated code
block, a retrieval cue, and a callout flagging a common mistake. The
test suite imports :func:`build_example_page` rather than duplicating
this construction, so the example and its tests can't drift apart.
"""

from __future__ import annotations

from handbook.learning.blocks import (
    Arrow,
    Callout,
    CodeAnnotation,
    CodeBlock,
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

_CPP_SOURCE = """\
int lo = 0, hi = n - 1, ans = n;
while (lo <= hi) {
    int mid = lo + (hi - lo) / 2;
    if (check(mid)) {
        ans = mid;
        hi = mid - 1;
    } else {
        lo = mid + 1;
    }
}
return ans;"""


def _intuition_section() -> Section:
    intuition = TextBlock(
        role=TextRole.INTUITION,
        content=RichText(
            spans=(
                Span(text="Binary search doesn't need a "),
                Span(text="sorted array", emphasis=(Emphasis.STRONG,)),
                Span(text="; it needs a "),
                Span(text="monotonic predicate", emphasis=(Emphasis.STRONG,)),
                Span(
                    text=(
                        " over the search space -- false, false, ..., "
                        "false, true, true, ..., true."
                    )
                ),
            )
        ),
    )
    insight = Callout(
        kind=CalloutKind.INSIGHT,
        title="The real requirement",
        body=(
            TextBlock(
                content=RichText.plain(
                    "If you can write a check(x) that is False then True "
                    "exactly once as x increases, you can binary search on "
                    "x -- even if x was never an array index to begin with."
                )
            ),
        ),
    )
    return Section(heading=RichText.plain("Intuition"), blocks=(intuition, insight))


def _walkthrough_section() -> Section:
    predicate_values = ["F", "F", "F", "T", "T", "T"]
    cells = tuple(
        VisualBlock(
            id=f"cell-{i}",
            role=ElementRole.VALUE,
            label=RichText.plain(f"check({i})"),
            value=value,
            position=ElementPosition(row=0, col=i),
        )
        for i, value in enumerate(predicate_values)
    )
    lo = VisualBlock(
        id="ptr-lo",
        role=ElementRole.POINTER,
        label=RichText.plain("lo"),
        value="0",
        position=ElementPosition(row=1, col=0),
        group="pointer",
    )
    mid = VisualBlock(
        id="ptr-mid",
        role=ElementRole.POINTER,
        label=RichText.plain("mid"),
        value="2",
        position=ElementPosition(row=1, col=2),
        group="pointer",
        emphasis=True,
    )
    hi = VisualBlock(
        id="ptr-hi",
        role=ElementRole.POINTER,
        label=RichText.plain("hi"),
        value="5",
        position=ElementPosition(row=1, col=5),
        group="pointer",
    )
    diagram = DiagramBlock(
        kind=DiagramKind.ARRAY,
        caption="Searching for the first index where check(mid) is True",
        layout_hint=LayoutHint.LINEAR,
        elements=(*cells, lo, mid, hi),
        arrows=(
            Arrow(
                from_id="ptr-mid",
                to_id="cell-2",
                label="check(mid) is False -> search the right half",
                order=1,
            ),
            Arrow(
                from_id="ptr-lo",
                to_id="cell-3",
                label="lo moves to mid + 1",
                order=2,
            ),
        ),
    )

    code = CodeBlock(
        language="cpp",
        caption="Binary search on the answer",
        source=_CPP_SOURCE,
        highlighted_lines=(3, 6),
        annotations=(
            CodeAnnotation(
                line=3, note="lo + (hi - lo) / 2 avoids overflow vs (lo + hi) / 2"
            ),
            CodeAnnotation(
                line=6,
                note="record the candidate, then keep searching left for an "
                "earlier True",
            ),
        ),
    )

    anchor = MemoryAnchor(
        target_id=code.id,
        prompt=RichText.plain(
            "Why hi = mid - 1, not hi = mid, when check(mid) is True?"
        ),
        anchor_type=AnchorType.QUESTION,
    )
    cue = ReviewCue(anchor_id=anchor.id, status=ReviewStatus.NEW)

    return Section(
        heading=RichText.plain("Walkthrough"),
        blocks=(diagram, code),
        memory_anchors=(anchor,),
        review_cues=(cue,),
    )


def _common_mistakes_section() -> Section:
    mistake = Callout(
        kind=CalloutKind.MISTAKE,
        title="Off-by-one on the boundary",
        body=(
            TextBlock(
                content=RichText.plain(
                    "Setting hi = mid instead of hi = mid - 1 when check(mid) "
                    "is False can loop forever if lo and hi converge without "
                    "either one shrinking."
                )
            ),
        ),
    )
    return Section(heading=RichText.plain("Common Mistakes"), blocks=(mistake,))


def build_example_page() -> Page:
    """Build the "Binary Search on the Answer" example page."""
    metadata = PageMetadata(
        title="Binary Search on the Answer",
        summary=(
            "Searching a monotonic predicate rather than a sorted array of "
            "values."
        ),
        tags=["binary-search", "monotonic-predicate"],
        source_kind="pattern",
        difficulty="Easy",
        estimated_minutes=15,
    )
    return Page(
        metadata=metadata,
        sections=(
            _intuition_section(),
            _walkthrough_section(),
            _common_mistakes_section(),
        ),
    )
