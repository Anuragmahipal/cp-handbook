"""``LayoutEngine``: decides how ``Section``s are grouped into rows.

The page never uses absolute positioning -- every row is a normal CSS
flex container, and cards inside a row share the row's width equally.
What ``LayoutEngine`` decides is *grouping*: which sections are light
enough to sit three-across, which pair up two-across, and which need
the full width of the page to themselves. That decision has to be
deterministic (the same ``Page`` always produces the same layout) and
content-driven (based on what's actually in a section, not a hardcoded
list of section titles this domain-agnostic representation has no
business knowing about).
"""

from __future__ import annotations

from dataclasses import dataclass

from handbook.learning.page import Section

_ROW_CAPACITY = 3.0
"""Total "weight units" a single row can hold before it's full."""

_MAX_COLUMNS = 3
"""Even if weight allows more, a row never holds more than this many
cards -- past three columns, a notebook page reads as a spreadsheet,
not a page."""

_HEAVY_THRESHOLD = 2.5
"""A section at or above this weight always gets a full-width row to
itself, regardless of what would otherwise fit next to it."""


def _section_weight(section: Section) -> float:
    """A deterministic, content-driven "how much room does this need"
    score for one section.

    Every contributing factor is a property of the section's own
    content (block types and counts) -- nothing here inspects heading
    text, so this works identically for a CP note and for a page about
    any other subject entirely.
    """
    has_diagram = any(block.block_type == "diagram" for block in section.blocks)
    if has_diagram:
        # A diagram needs width to stay legible -- always heavy, a
        # deliberate special case rather than a value tuned to just
        # barely cross the threshold below.
        return 3.0

    weight = 1.0
    has_code = any(block.block_type == "code" for block in section.blocks)
    if has_code:
        weight += 0.5
    extra_blocks = max(0, len(section.blocks) - 2)
    weight += 0.15 * extra_blocks
    return min(weight, 3.0)


@dataclass(frozen=True, slots=True)
class LayoutRow:
    """One horizontal row of the page: one or more sections, rendered
    as equal-width cards sharing the row."""

    sections: tuple[Section, ...]


@dataclass(frozen=True, slots=True)
class LayoutPlan:
    """The full, ordered arrangement of a page's sections into rows."""

    rows: tuple[LayoutRow, ...]


class LayoutEngine:
    """Groups a page's sections into rows, in original reading order."""

    def plan(self, sections: tuple[Section, ...]) -> LayoutPlan:
        rows: list[LayoutRow] = []
        current: list[Section] = []
        current_weight = 0.0

        def flush() -> None:
            nonlocal current, current_weight
            if current:
                rows.append(LayoutRow(sections=tuple(current)))
            current = []
            current_weight = 0.0

        for section in sections:
            weight = _section_weight(section)
            if weight >= _HEAVY_THRESHOLD:
                flush()
                rows.append(LayoutRow(sections=(section,)))
                continue
            would_exceed_capacity = current_weight + weight > _ROW_CAPACITY
            would_exceed_columns = len(current) >= _MAX_COLUMNS
            if current and (would_exceed_capacity or would_exceed_columns):
                flush()
            current.append(section)
            current_weight += weight

        flush()
        return LayoutPlan(rows=tuple(rows))
