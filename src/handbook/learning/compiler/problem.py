"""``ProblemCompiler``: projects a ``Problem`` KnowledgeItem into a ``Page``.

Section plan:

======================  =======================================================
Section                 Source
======================  =======================================================
Overview                platform / contest / index / rating / source /
                        solved / attempts / time spent -- always present,
                        since ``platform``/``contest``/``index`` are required
                        fields (see ``handbook.models.problem.Problem``)
Algorithms Used         ``Problem.algorithms`` (graph)
Patterns Used           ``Problem.patterns`` (graph)
Mistakes                ``Problem.mistakes`` merged with every
                        ``Mistake.related_problems`` backlink (graph), plus
                        a mechanical "N attempts before solving" callout
                        when ``attempts > 1``
Prerequisites           ``KnowledgeItem.prerequisites`` (graph)
======================  =======================================================

``Problem`` carries no free-form "solution" or "approach" field of its
own -- what's mechanically derivable from Codeforces metadata already
lives in ``handbook.sync.revision_note.RevisionNote`` instead (see that
module's docstring: everything requiring actual understanding of a
solution is deliberately left for a human to fill in). This compiler
stays consistent with that boundary: it never fabricates a "Core Idea"
or "Approach" section from nothing.
"""

from __future__ import annotations

from handbook.learning.compiler.base import Compiler
from handbook.learning.compiler.context import CompilationContext
from handbook.learning.compiler.helpers import (
    base_metadata,
    bulleted_callout,
    build_page,
    linked_list_block,
    merge_pairs,
    plain_section,
    plain_text_block,
    prerequisites_section,
    related_pairs,
    related_section,
    section_with_anchor,
)
from handbook.learning.compiler.result import CompilationResult
from handbook.learning.enums import CalloutKind
from handbook.models.problem import Problem


class ProblemCompiler(Compiler[Problem]):
    item_type = Problem

    def compile(self, item: Problem, context: CompilationContext) -> CompilationResult:
        warnings: list[str] = []

        overview_block = plain_text_block(item, "block:overview", _overview_text(item))
        overview_section = section_with_anchor(
            item,
            "overview",
            "Overview",
            (overview_block,),
            prompt_text=f"What signaled the approach for {item.title}?",
            target_id=overview_block.id,
        )
        sections = [overview_section]

        algorithms = related_pairs(context, item, field_name="algorithms", direction="out")
        algorithms_section = related_section(item, "algorithms", "Algorithms Used", algorithms)
        if algorithms_section is not None:
            sections.append(algorithms_section)
        else:
            warnings.append("no algorithms recorded in the graph.")

        patterns = related_pairs(context, item, field_name="patterns", direction="out")
        patterns_section = related_section(item, "patterns", "Patterns Used", patterns)
        if patterns_section is not None:
            sections.append(patterns_section)
        else:
            warnings.append("no patterns recorded in the graph.")

        mistake_blocks = []
        if item.attempts > 1:
            plural = "attempt" if item.attempts == 1 else "attempts"
            mistake_blocks.append(
                bulleted_callout(
                    item,
                    "block:attempt-history",
                    kind=CalloutKind.MISTAKE,
                    title="Attempt History",
                    lines=[f"Took {item.attempts} {plural} before solving."],
                )
            )
        mistake_pairs = merge_pairs(
            related_pairs(context, item, field_name="mistakes", direction="out"),
            related_pairs(
                context, item, field_name="related_problems", direction="in", other_kind="mistake"
            ),
        )
        if mistake_pairs:
            mistake_blocks.append(linked_list_block(item, "block:mistakes:list", mistake_pairs))
        if mistake_blocks:
            sections.append(plain_section(item, "mistakes", "Mistakes", mistake_blocks))
        else:
            warnings.append("no mistakes recorded for this problem.")

        prerequisites = prerequisites_section(context, item)
        if prerequisites is not None:
            sections.append(prerequisites)
        else:
            warnings.append("no prerequisites recorded in the graph.")

        difficulty_override = None
        if item.difficulty is None and item.rating is not None:
            difficulty_override = str(item.rating)
        metadata = base_metadata(
            item,
            source_kind=item.kind,
            summary=_summary(item),
            estimated_minutes=item.time_spent_minutes,
            difficulty_override=difficulty_override,
        )
        page = build_page(item, metadata, sections)
        return CompilationResult(item=item, page=page, warnings=warnings)


def _overview_text(item: Problem) -> str:
    parts = [f"{item.platform.value} · Contest {item.contest} · Problem {item.index}"]
    if item.rating is not None:
        parts.append(f"rated {item.rating}")
    parts.append(f"source: {item.source.value}")
    headline = " · ".join(parts) + "."

    if item.solved:
        status = f"Solved in {item.attempts} attempt(s)."
    else:
        status = f"Not yet solved ({item.attempts} attempt(s) so far)."
    if item.time_spent_minutes is not None:
        status += f" Time to solve: {item.time_spent_minutes} min."
    return f"{headline} {status}"


def _summary(item: Problem) -> str:
    parts = [item.platform.value, item.contest, item.index]
    if item.rating is not None:
        parts.append(f"({item.rating})")
    return " ".join(parts)
