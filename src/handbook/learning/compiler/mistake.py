"""``MistakeCompiler``: projects a ``Mistake`` KnowledgeItem into a ``Page``.

Section plan:

======================  =======================================================
Section                 Source
======================  =======================================================
What Happened           ``Mistake.notes`` (inherited free text), falling back
                        to a templated sentence from ``category``/
                        ``occurrences`` when ``notes`` is empty -- always
                        present, since ``category`` and ``occurrences`` both
                        have defaults (see ``handbook.models.mistake.Mistake``)
Root Cause              ``Mistake.cause``
Prevention              ``Mistake.prevention``
Related Problems        ``Mistake.related_problems`` (graph)
Related Algorithms      ``Mistake.related_algorithms`` (graph -- covers both
                        ``Algorithm`` and ``Pattern`` targets, since the
                        underlying relation is resolved by title/slug, not
                        by target kind)
Prerequisites           ``KnowledgeItem.prerequisites`` (graph)
======================  =======================================================

The default memory anchor prefers "Prevention" (the same section
``examples/mistake_page.json`` anchors its own hand-authored cue to),
falling back to "Root Cause" and then "What Happened" -- the one
section every ``Mistake`` is guaranteed to have, however sparse.
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
from handbook.models.mistake import Mistake


class MistakeCompiler(Compiler[Mistake]):
    item_type = Mistake

    def compile(self, item: Mistake, context: CompilationContext) -> CompilationResult:
        warnings: list[str] = []
        specs = []

        happened_block = plain_text_block(item, "block:what-happened", _what_happened_text(item))
        specs.append(("what-happened", "What Happened", (happened_block,)))
        if not item.notes.strip():
            warnings.append("notes is empty; What Happened used a templated fallback.")

        cause_callout = None
        if item.cause.strip():
            cause_callout = bulleted_callout(
                item,
                "block:root-cause",
                kind=CalloutKind.PITFALL,
                title="Root Cause",
                lines=[item.cause],
            )
            specs.append(("root-cause", "Root Cause", (cause_callout,)))
        else:
            warnings.append("cause is empty; Root Cause section omitted.")

        prevention_callout = None
        if item.prevention.strip():
            prevention_callout = bulleted_callout(
                item,
                "block:prevention",
                kind=CalloutKind.TIP,
                title="Prevention",
                lines=[item.prevention],
            )
            specs.append(("prevention", "Prevention", (prevention_callout,)))
        else:
            warnings.append("prevention is empty; Prevention section omitted.")

        anchor = pick_anchor(
            (
                "prevention",
                prevention_callout.id if prevention_callout else None,
                f"How do you prevent {item.title} from recurring?",
            ),
            (
                "root-cause",
                cause_callout.id if cause_callout else None,
                f"What causes {item.title}?",
            ),
            ("what-happened", happened_block.id, f"What happened in {item.title}?"),
        )
        sections = sections_with_optional_anchor(item, specs, anchor)

        related_problems = related_pairs(
            context, item, field_name="related_problems", direction="out"
        )
        related_problems_section = related_section(
            item, "related-problems", "Related Problems", related_problems
        )
        if related_problems_section is not None:
            sections.append(related_problems_section)
        else:
            warnings.append("no related problems found in the graph.")

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

        prerequisites = prerequisites_section(context, item)
        if prerequisites is not None:
            sections.append(prerequisites)
        else:
            warnings.append("no prerequisites recorded in the graph.")

        metadata = base_metadata(item, source_kind=item.kind, summary=_summary(item))
        page = build_page(item, metadata, sections)
        return CompilationResult(item=item, page=page, warnings=warnings)


def _what_happened_text(item: Mistake) -> str:
    if item.notes.strip():
        return item.notes
    plural = "time" if item.occurrences == 1 else "times"
    return f"{item.category.value}, recorded {item.occurrences} {plural}."


def _summary(item: Mistake) -> str:
    if item.cause.strip():
        first_sentence = item.cause.strip().split(". ")[0].rstrip(".")
        return f"{first_sentence}."
    return f"{item.category.value} -- recorded {item.occurrences}x."
