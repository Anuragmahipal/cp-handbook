"""``AlgorithmCompiler``: projects an ``Algorithm`` KnowledgeItem into a ``Page``.

Section plan, one section per field that's actually populated:

======================  =======================================================
Section                 Source
======================  =======================================================
Intuition               ``Algorithm.intuition``
Complexity              ``Algorithm.time_complexity`` / ``space_complexity``
Implementation          ``Algorithm.implementation`` (as a code block)
Pitfalls                ``Algorithm.pitfalls``
Prerequisites           ``KnowledgeItem.prerequisites`` (graph)
Related Problems        ``Algorithm.related_problems`` merged with every
                        ``Problem.algorithms`` backlink (graph)
Related Patterns        every ``Pattern.related_algorithms`` backlink (graph)
Mistakes                every ``Mistake.related_algorithms`` backlink (graph)
Learning Progress       ``handbook.evolution.stats.algorithm_evolution_stats``
                        -- total/first/latest solve, solve frequency,
                        learning velocity (Part 2). Omitted unless a
                        ``CompilationContext.evolution`` log was supplied
                        and this algorithm has at least one recorded solve.
Rating Histogram        ditto, as a ``DiagramBlock`` bar chart
Recent Activity         ditto, last 5 solves
Learning History        every recorded evolution event for this item, in
                        order (Part 4) -- shared with every other compiler
                        via ``handbook.learning.compiler.helpers.
                        learning_history_section``
======================  =======================================================

Deliberately named after what the domain model actually stores
(``Intuition``, not the example fixture's ``Recognition``/``Core Idea``
split) rather than mimicking ``examples/algorithm_page.json``'s hand-
authored heading taxonomy -- that fixture's "Recognition" section
combines ``intuition`` with a second, distinct insight ("when it stops
applying") that doesn't correspond to any domain-model field. Inventing
that split here would mean fabricating content the source
``KnowledgeItem`` was never given, which is exactly what the "Do NOT
use AI" constraint rules out. See
``tests/test_compiler_examples_comparison.py`` for how the two are
compared without expecting them to match section-for-section.
"""

from __future__ import annotations

from handbook.evolution.stats import AlgorithmEvolutionStats, algorithm_evolution_stats
from handbook.learning.blocks import CodeBlock, DiagramBlock, VisualBlock
from handbook.learning.compiler.base import Compiler
from handbook.learning.compiler.context import CompilationContext
from handbook.learning.compiler.helpers import (
    base_metadata,
    bulleted_callout,
    build_page,
    learning_history_section,
    merge_pairs,
    pick_anchor,
    plain_section,
    plain_text_block,
    prerequisites_section,
    related_pairs,
    related_section,
    sections_with_optional_anchor,
    stable_id,
)
from handbook.learning.compiler.result import CompilationResult
from handbook.learning.enums import CalloutKind, DiagramKind, TextRole
from handbook.learning.page import Section
from handbook.learning.richtext import RichText
from handbook.models.algorithm import Algorithm

_DEFAULT_CODE_LANGUAGE = "cpp"
"""``Algorithm.implementation`` carries no language of its own (see
``handbook.models.algorithm.Algorithm``) -- every code fixture already
checked into this vault is C++, so that's the compiler's default
rather than guessing per-item from the source text. Called out here,
not hidden, the same way ``handbook.sync.DEVELOPER_NOTES_SYNC.md``
calls out its own known simplifications.
"""


class AlgorithmCompiler(Compiler[Algorithm]):
    item_type = Algorithm

    def compile(self, item: Algorithm, context: CompilationContext) -> CompilationResult:
        warnings: list[str] = []
        specs = []

        intuition_block = None
        if item.intuition.strip():
            intuition_block = plain_text_block(
                item, "block:intuition", item.intuition, role=TextRole.INTUITION
            )
            specs.append(("intuition", "Intuition", (intuition_block,)))
        else:
            warnings.append("intuition is empty; Intuition section omitted.")

        if item.time_complexity or item.space_complexity:
            complexity_block = plain_text_block(
                item, "block:complexity", _complexity_text(item)
            )
            specs.append(("complexity", "Complexity", (complexity_block,)))
        else:
            warnings.append(
                "time_complexity/space_complexity are both empty; "
                "Complexity section omitted."
            )

        code_block = None
        if item.implementation.strip():
            code_block = CodeBlock(
                id=stable_id(item, "block:implementation"),
                language=_DEFAULT_CODE_LANGUAGE,
                source=item.implementation,
            )
            specs.append(("implementation", "Implementation", (code_block,)))
        else:
            warnings.append("implementation is empty; Implementation section omitted.")

        pitfalls_callout = None
        if item.pitfalls:
            pitfalls_callout = bulleted_callout(
                item,
                "block:pitfalls",
                kind=CalloutKind.PITFALL,
                title="Pitfalls",
                lines=item.pitfalls,
            )
            specs.append(("pitfalls", "Pitfalls", (pitfalls_callout,)))
        else:
            warnings.append("pitfalls is empty; Pitfalls section omitted.")

        anchor = pick_anchor(
            ("implementation", code_block.id if code_block else None, _implementation_prompt(item)),
            ("intuition", intuition_block.id if intuition_block else None, _intuition_prompt(item)),
            ("pitfalls", pitfalls_callout.id if pitfalls_callout else None, _pitfall_prompt(item)),
        )
        if anchor is None:
            warnings.append("no reviewable content found; no memory anchor generated.")

        sections = sections_with_optional_anchor(item, specs, anchor)

        prerequisites = prerequisites_section(context, item)
        if prerequisites is not None:
            sections.append(prerequisites)
        else:
            warnings.append("no prerequisites recorded in the graph.")

        related_problems = merge_pairs(
            related_pairs(context, item, field_name="related_problems", direction="out"),
            related_pairs(
                context, item, field_name="algorithms", direction="in", other_kind="problem"
            ),
        )
        related_problems_section = related_section(
            item, "related-problems", "Related Problems", related_problems
        )
        if related_problems_section is not None:
            sections.append(related_problems_section)
        else:
            warnings.append("no related problems found in the graph.")

        related_patterns = related_pairs(
            context, item, field_name="related_algorithms", direction="in", other_kind="pattern"
        )
        related_patterns_section = related_section(
            item, "related-patterns", "Related Patterns", related_patterns
        )
        if related_patterns_section is not None:
            sections.append(related_patterns_section)
        else:
            warnings.append("no related patterns found in the graph.")

        mistakes = related_pairs(
            context, item, field_name="related_algorithms", direction="in", other_kind="mistake"
        )
        mistakes_section = related_section(item, "mistakes", "Mistakes", mistakes)
        if mistakes_section is not None:
            sections.append(mistakes_section)
        else:
            warnings.append("no related mistakes found in the graph.")

        history = learning_history_section(context, item)
        if history is not None:
            sections.append(history)

        if context.evolution is not None:
            stats = algorithm_evolution_stats(context.graph, item.id, "algorithms", context.items_by_id)
            if stats.total_solves > 0:
                sections.append(_learning_progress_section(item, stats))
                if stats.rating_histogram:
                    sections.append(_rating_histogram_section(item, stats))
                if stats.recent_activity:
                    sections.append(_recent_activity_section(item, stats))
            else:
                warnings.append("no recorded solves yet; Learning Progress sections omitted.")

        metadata = base_metadata(
            item,
            source_kind=item.kind,
            summary=_summary(item),
        )
        page = build_page(item, metadata, sections)
        return CompilationResult(item=item, page=page, warnings=warnings)


def _complexity_text(item: Algorithm) -> str:
    parts = []
    if item.time_complexity:
        parts.append(f"Time: {item.time_complexity}")
    if item.space_complexity:
        parts.append(f"Space: {item.space_complexity}")
    return " · ".join(parts)


def _summary(item: Algorithm) -> str:
    if item.intuition.strip():
        first_sentence = item.intuition.strip().split(". ")[0].rstrip(".")
        return f"{first_sentence}."
    if item.category is not None:
        return f"A {item.category.value} technique."
    return ""


def _implementation_prompt(item: Algorithm) -> str:
    return f"How does {item.title} work, step by step?"


def _intuition_prompt(item: Algorithm) -> str:
    return f"What's the core intuition behind {item.title}?"


def _pitfall_prompt(item: Algorithm) -> str:
    return f"What's the pitfall to watch for in {item.title}?"


def _learning_progress_section(item: Algorithm, stats: AlgorithmEvolutionStats) -> Section:
    parts = [
        f"Solved {stats.total_solves} problem{'s' if stats.total_solves != 1 else ''} "
        "using this so far."
    ]
    if stats.first_solve is not None:
        parts.append(f"First solved {stats.first_solve.date().isoformat()}.")
    if stats.latest_solve is not None:
        parts.append(f"Most recently {stats.latest_solve.date().isoformat()}.")
    if stats.solve_frequency_per_week is not None:
        parts.append(f"About {stats.solve_frequency_per_week} problem(s) per week on average.")
    parts.append(
        f"{stats.learning_velocity_per_two_weeks} solve(s) in the most recent "
        "2-week window of activity."
    )
    block = plain_text_block(item, "block:evolution-progress", " ".join(parts))
    return plain_section(item, "evolution-progress", "Learning Progress", (block,))


def _rating_histogram_section(item: Algorithm, stats: AlgorithmEvolutionStats) -> Section:
    elements = tuple(
        VisualBlock(
            id=stable_id(item, f"evolution:histogram:{index}"),
            label=RichText.plain(bucket.label),
            value=str(bucket.count),
        )
        for index, bucket in enumerate(stats.rating_histogram)
    )
    diagram = DiagramBlock(
        id=stable_id(item, "evolution:histogram"),
        kind=DiagramKind.OTHER,
        caption="Problems solved, grouped by rating band",
        elements=elements,
    )
    return plain_section(item, "rating-histogram", "Rating Histogram", (diagram,))


def _recent_activity_section(item: Algorithm, stats: AlgorithmEvolutionStats) -> Section:
    lines = [
        f"{when.date().isoformat()} \u2014 {title}" for title, when in stats.recent_activity
    ]
    callout = bulleted_callout(
        item, "block:recent-activity", kind=CalloutKind.TIP, title="Recent Activity", lines=lines
    )
    return plain_section(item, "recent-activity", "Recent Activity", (callout,))
