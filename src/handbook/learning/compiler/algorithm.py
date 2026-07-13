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

from handbook.learning.blocks import CodeBlock
from handbook.learning.compiler.base import Compiler
from handbook.learning.compiler.context import CompilationContext
from handbook.learning.compiler.helpers import (
    base_metadata,
    bulleted_callout,
    build_page,
    merge_pairs,
    pick_anchor,
    plain_text_block,
    prerequisites_section,
    related_pairs,
    related_section,
    sections_with_optional_anchor,
    stable_id,
)
from handbook.learning.compiler.result import CompilationResult
from handbook.learning.enums import CalloutKind, TextRole
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
