"""Large-vault compilation: build a few hundred interrelated
``KnowledgeItem``s, build one graph over all of them, and compile every
item through :class:`~handbook.learning.compiler.KnowledgeCompiler`.

Verifies two things a small hand-written fixture can't: that
compilation genuinely scales (no accidental O(n^2) blowup -- see
``docs/ARCHITECTURE_NOTES_COMPILER.md``'s performance notes on why
``related_pairs()`` is O(edges touching that one item), not O(total
graph edges)), and that every compiled page -- not just a couple of
examples -- is internally valid and round-trips.
"""

from __future__ import annotations

import time

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.learning.serialization import dump_page, load_page
from handbook.models import Algorithm, Mistake, Pattern, Platform, Problem

_N_ALGORITHMS = 40
_N_PATTERNS = 20
_N_PROBLEMS = 150
_N_MISTAKES = 30


def _build_vault() -> list:
    algorithms = [
        Algorithm(
            title=f"Algorithm {i}",
            intuition=f"Intuition for algorithm {i}.",
            implementation=f"solve_{i}();",
            time_complexity="O(n log n)",
            pitfalls=[f"pitfall {i}-a", f"pitfall {i}-b"],
            # every algorithm past the first ten depends on an earlier one
            prerequisites=[f"Algorithm {i - 10}"] if i >= 10 else [],
        )
        for i in range(_N_ALGORITHMS)
    ]
    patterns = [
        Pattern(
            title=f"Pattern {i}",
            description=f"Description for pattern {i}.",
            recognition_cues=[f"cue {i}"],
            related_algorithms=[f"Algorithm {i % _N_ALGORITHMS}"],
        )
        for i in range(_N_PATTERNS)
    ]
    mistakes = [
        Mistake(
            title=f"Mistake {i}",
            cause=f"Cause {i}",
            prevention=f"Prevention {i}",
            related_algorithms=[f"Algorithm {i % _N_ALGORITHMS}"],
        )
        for i in range(_N_MISTAKES)
    ]
    problems = [
        Problem(
            title=f"Problem {i}",
            platform=Platform.CODEFORCES,
            contest=str(i // 5),
            index=chr(ord("A") + (i % 5)),
            rating=800 + (i % 20) * 100,
            algorithms=[f"Algorithm {i % _N_ALGORITHMS}"],
            patterns=[f"Pattern {i % _N_PATTERNS}"],
            mistakes=[f"Mistake {i % _N_MISTAKES}"] if i % 3 == 0 else [],
            attempts=1 + (i % 4),
        )
        for i in range(_N_PROBLEMS)
    ]
    return [*algorithms, *patterns, *mistakes, *problems]


def test_large_vault_compiles_entirely_without_error():
    items = _build_vault()
    graph = GraphBuilder(items).build()
    compiler = KnowledgeCompiler(graph)

    start = time.perf_counter()
    results = compiler.compile_all(items)
    elapsed = time.perf_counter() - start

    assert len(results) == len(items)
    # Generous bound: this is pure in-memory object construction, no I/O.
    # Not a tight perf assertion -- just a guard against an accidental
    # quadratic blowup in graph traversal.
    assert elapsed < 10.0, f"compiling {len(items)} items took {elapsed:.2f}s"


def test_large_vault_every_page_round_trips():
    items = _build_vault()
    graph = GraphBuilder(items).build()
    compiler = KnowledgeCompiler(graph)

    for item in items:
        result = compiler.compile(item)
        loaded = load_page(dump_page(result.page))
        assert loaded == result.page


def test_large_vault_relation_sections_have_no_dangling_link_targets():
    """Every ``link_target`` a compiled page emits must point at a real
    (possibly shadow) node id that actually exists in the graph --
    never an arbitrary string."""
    items = _build_vault()
    graph = GraphBuilder(items).build()
    compiler = KnowledgeCompiler(graph)
    known_ids = {node.id for node in graph.nodes()}

    checked_any = False
    for item in items[:60]:  # a representative subset keeps this test fast
        result = compiler.compile(item)
        for section in result.page.sections:
            for block in section.blocks:
                if block.block_type != "text":
                    continue
                for span in block.content.spans:
                    if span.link_target:
                        checked_any = True
                        assert span.link_target in known_ids

    assert checked_any, "expected at least one relation link in this subset"


def test_large_vault_prerequisite_chain_resolves_correctly():
    items = _build_vault()
    graph = GraphBuilder(items).build()
    compiler = KnowledgeCompiler(graph)

    algo_20 = next(i for i in items if getattr(i, "title", "") == "Algorithm 20")
    result = compiler.compile(algo_20)
    prereq_section = next(
        s for s in result.page.sections if s.heading.as_plain_text() == "Prerequisites"
    )
    assert "Algorithm 10" in prereq_section.blocks[0].content.as_plain_text()
