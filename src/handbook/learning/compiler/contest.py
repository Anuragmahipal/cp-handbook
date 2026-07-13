"""``ContestCompiler``: projects a ``Contest`` KnowledgeItem into a ``Page``.

Section plan:

======================  =======================================================
Section                 Source
======================  =======================================================
Overview                platform / contest_type / start_time / duration /
                        rank / rating_change / performance_rating -- always
                        present, since ``platform``/``contest_type`` are
                        required/defaulted fields (see
                        ``handbook.models.contest.Contest``)
Problems                ``Contest.problems`` (graph)
Takeaways               ``Contest.takeaways``
Prerequisites           ``KnowledgeItem.prerequisites`` (graph)
======================  =======================================================

The default memory anchor prefers "Takeaways" (the most reviewable
content a contest note has -- a lesson worth being quizzed on),
falling back to "Overview", the one section every ``Contest`` is
guaranteed to have.
"""

from __future__ import annotations

from handbook.learning.compiler.base import Compiler
from handbook.learning.compiler.context import CompilationContext
from handbook.learning.compiler.helpers import (
    base_metadata,
    build_page,
    bulleted_callout,
    pick_anchor,
    plain_text_block,
    prerequisites_section,
    related_pairs,
    related_section,
    sections_with_optional_anchor,
)
from handbook.learning.compiler.result import CompilationResult
from handbook.learning.enums import CalloutKind
from handbook.models.contest import Contest


class ContestCompiler(Compiler[Contest]):
    item_type = Contest

    def compile(self, item: Contest, context: CompilationContext) -> CompilationResult:
        warnings: list[str] = []
        specs = []

        overview_block = plain_text_block(item, "block:overview", _overview_text(item))
        specs.append(("overview", "Overview", (overview_block,)))

        takeaways_callout = None
        if item.takeaways:
            takeaways_callout = bulleted_callout(
                item,
                "block:takeaways",
                kind=CalloutKind.INSIGHT,
                title="Takeaways",
                lines=item.takeaways,
            )
            specs.append(("takeaways", "Takeaways", (takeaways_callout,)))
        else:
            warnings.append("takeaways is empty; Takeaways section omitted.")

        anchor = pick_anchor(
            (
                "takeaways",
                takeaways_callout.id if takeaways_callout else None,
                f"What was the key takeaway from {item.title}?",
            ),
            ("overview", overview_block.id, f"What happened during {item.title}?"),
        )
        sections = sections_with_optional_anchor(item, specs, anchor)

        problems = related_pairs(context, item, field_name="problems", direction="out")
        problems_section = related_section(item, "problems", "Problems", problems)
        if problems_section is not None:
            sections.append(problems_section)
        else:
            warnings.append("no problems recorded in the graph.")

        prerequisites = prerequisites_section(context, item)
        if prerequisites is not None:
            sections.append(prerequisites)
        else:
            warnings.append("no prerequisites recorded in the graph.")

        metadata = base_metadata(
            item,
            source_kind=item.kind,
            summary=_summary(item),
            estimated_minutes=item.duration_minutes,
        )
        page = build_page(item, metadata, sections)
        return CompilationResult(item=item, page=page, warnings=warnings)


def _overview_text(item: Contest) -> str:
    parts = [f"{item.platform.value} · {item.contest_type.value}"]
    if item.start_time is not None:
        parts.append(item.start_time.strftime("%Y-%m-%d"))
    if item.duration_minutes is not None:
        parts.append(f"{item.duration_minutes} min")
    headline = " · ".join(parts) + "."

    results = []
    if item.rank is not None:
        results.append(f"Rank {item.rank}")
    if item.rating_change is not None:
        sign = "+" if item.rating_change >= 0 else ""
        results.append(f"rating {sign}{item.rating_change}")
    if item.performance_rating is not None:
        results.append(f"performance {item.performance_rating}")
    if results:
        headline += " " + ", ".join(results) + "."
    return headline


def _summary(item: Contest) -> str:
    return f"{item.platform.value} {item.contest_type.value} contest."
