"""``PatternCompiler``: projects a ``Pattern`` KnowledgeItem into a ``Page``.

Section plan:

======================  =======================================================
Section                 Source
======================  =======================================================
Intuition               ``Pattern.description``
Recognition Cues        ``Pattern.recognition_cues``
Related Algorithms      ``Pattern.related_algorithms`` (graph)
Example Problems        ``Pattern.example_problems`` (graph)
Mistakes                every ``Mistake.related_algorithms`` backlink whose
                        target resolves to this pattern (graph)
Prerequisites           ``KnowledgeItem.prerequisites`` (graph)
======================  =======================================================
"""

from __future__ import annotations

from handbook.learning.compiler.base import Compiler
from handbook.learning.compiler.context import CompilationContext
from handbook.learning.compiler.helpers import (
    base_metadata,
    build_page,
    bulleted_callout,
    learning_history_section,
    pick_anchor,
    plain_text_block,
    prerequisites_section,
    related_pairs,
    related_section,
    sections_with_optional_anchor,
)
from handbook.learning.compiler.result import CompilationResult
from handbook.learning.enums import CalloutKind, TextRole
from handbook.models.pattern import Pattern


class PatternCompiler(Compiler[Pattern]):
    item_type = Pattern

    def compile(self, item: Pattern, context: CompilationContext) -> CompilationResult:
        warnings: list[str] = []
        specs = []

        intuition_block = None
        if item.description.strip():
            intuition_block = plain_text_block(
                item, "block:intuition", item.description, role=TextRole.INTUITION
            )
            specs.append(("intuition", "Intuition", (intuition_block,)))
        else:
            warnings.append("description is empty; Intuition section omitted.")

        cues_callout = None
        if item.recognition_cues:
            cues_callout = bulleted_callout(
                item,
                "block:recognition-cues",
                kind=CalloutKind.TIP,
                title="Recognition Cues",
                lines=item.recognition_cues,
            )
            specs.append(("recognition-cues", "Recognition Cues", (cues_callout,)))
        else:
            warnings.append("recognition_cues is empty; Recognition Cues section omitted.")

        anchor = pick_anchor(
            ("recognition-cues", cues_callout.id if cues_callout else None, _cue_prompt(item)),
            ("intuition", intuition_block.id if intuition_block else None, _intuition_prompt(item)),
        )
        if anchor is None:
            warnings.append("no reviewable content found; no memory anchor generated.")

        sections = sections_with_optional_anchor(item, specs, anchor)

        related_algorithms = related_pairs(
            context, item, field_name="related_algorithms", direction="out"
        )
        related_algorithms_section = related_section(
            item, "related-algorithms", "Related Algorithms", related_algorithms
        )
        if related_algorithms_section is not None:
            sections.append(related_algorithms_section)
        else:
            warnings.append("no related algorithms found in the graph.")

        example_problems = related_pairs(
            context, item, field_name="example_problems", direction="out"
        )
        example_problems_section = related_section(
            item, "example-problems", "Example Problems", example_problems
        )
        if example_problems_section is not None:
            sections.append(example_problems_section)
        else:
            warnings.append("no example problems found in the graph.")

        mistakes = related_pairs(
            context, item, field_name="related_algorithms", direction="in", other_kind="mistake"
        )
        mistakes_section = related_section(item, "mistakes", "Mistakes", mistakes)
        if mistakes_section is not None:
            sections.append(mistakes_section)
        else:
            warnings.append("no related mistakes found in the graph.")

        prerequisites = prerequisites_section(context, item)
        if prerequisites is not None:
            sections.append(prerequisites)
        else:
            warnings.append("no prerequisites recorded in the graph.")

        history = learning_history_section(context, item)
        if history is not None:
            sections.append(history)

        metadata = base_metadata(item, source_kind=item.kind, summary=_summary(item))
        page = build_page(item, metadata, sections)
        return CompilationResult(item=item, page=page, warnings=warnings)


def _summary(item: Pattern) -> str:
    if item.description.strip():
        first_sentence = item.description.strip().split(". ")[0].rstrip(".")
        return f"{first_sentence}."
    if item.category is not None:
        return f"A {item.category.value} pattern."
    return ""


def _cue_prompt(item: Pattern) -> str:
    return f"What's the recognition cue for {item.title}?"


def _intuition_prompt(item: Pattern) -> str:
    return f"When does {item.title} apply?"
