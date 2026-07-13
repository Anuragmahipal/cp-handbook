"""Determinism tests for the compiler layer.

Two distinct claims, mirroring the pattern
``ARCHITECTURE_NOTES_NOTEBOOK.md`` already establishes for the renderer:

* **Idempotency** -- compiling the *same* ``KnowledgeItem`` object
  twice against the *same* graph produces byte-identical output.
* **Cross-object determinism** -- two *separately constructed*
  ``KnowledgeItem`` objects with identical field values (including the
  same explicit ``id``/timestamps) compile to byte-identical output --
  i.e. the compiler is a pure function of content, not of incidental
  object identity or construction order.
"""

from __future__ import annotations

from datetime import datetime

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.learning.serialization import dump_page
from handbook.models import Algorithm, Contest, Mistake, Pattern, Platform, Problem

_FIXED_ID = "11111111-1111-1111-1111-111111111111"
_FIXED_CREATED = datetime(2026, 1, 1, 9, 0, 0)
_FIXED_UPDATED = datetime(2026, 1, 2, 10, 30, 0)


def _algorithm(**overrides) -> Algorithm:
    fields = dict(
        id=_FIXED_ID,
        title="Binary Lifting",
        intuition="Precompute 2^k ancestors.",
        implementation="up[k][v] = up[k-1][up[k-1][v]];",
        time_complexity="O(log n)",
        pitfalls=["off-by-one"],
        created_at=_FIXED_CREATED,
        updated_at=_FIXED_UPDATED,
    )
    fields.update(overrides)
    return Algorithm(**fields)


def test_idempotency_same_object_compiled_twice():
    algo = _algorithm()
    graph = GraphBuilder([algo]).build()
    compiler = KnowledgeCompiler(graph)

    first = compiler.compile(algo)
    second = compiler.compile(algo)

    assert dump_page(first.page) == dump_page(second.page)


def test_cross_object_determinism_same_content_different_instances():
    algo_a = _algorithm()
    algo_b = _algorithm()  # a fresh, separately-constructed but content-identical object
    assert algo_a is not algo_b

    graph = GraphBuilder([algo_a]).build()
    compiler = KnowledgeCompiler(graph)

    result_a = compiler.compile(algo_a)
    result_b = compiler.compile(algo_b)

    assert dump_page(result_a.page) == dump_page(result_b.page)


def test_determinism_with_graph_relations_present():
    algo = _algorithm(related_problems=["P"])
    problem = Problem(
        id="22222222-2222-2222-2222-222222222222",
        title="P",
        platform=Platform.CODEFORCES,
        contest="1",
        index="A",
        algorithms=["Binary Lifting"],
        created_at=_FIXED_CREATED,
        updated_at=_FIXED_UPDATED,
    )
    graph = GraphBuilder([algo, problem]).build()
    compiler = KnowledgeCompiler(graph)

    first = compiler.compile(algo)
    second = compiler.compile(algo)
    assert dump_page(first.page) == dump_page(second.page)


def test_determinism_across_every_compiler():
    """One representative, fully-populated item per kind -- each compiled
    twice against a fixed graph must produce identical output."""
    algo = Algorithm(id=_FIXED_ID, title="A", intuition="x", created_at=_FIXED_CREATED, updated_at=_FIXED_UPDATED)
    pattern = Pattern(
        id="33333333-3333-3333-3333-333333333333",
        title="Pat",
        description="y",
        recognition_cues=["cue"],
        created_at=_FIXED_CREATED,
        updated_at=_FIXED_UPDATED,
    )
    mistake = Mistake(
        id="44444444-4444-4444-4444-444444444444",
        title="M",
        cause="c",
        prevention="p",
        created_at=_FIXED_CREATED,
        updated_at=_FIXED_UPDATED,
    )
    problem = Problem(
        id="55555555-5555-5555-5555-555555555555",
        title="Prob",
        platform=Platform.CODEFORCES,
        contest="1",
        index="A",
        created_at=_FIXED_CREATED,
        updated_at=_FIXED_UPDATED,
    )
    contest = Contest(
        id="66666666-6666-6666-6666-666666666666",
        title="Contest",
        platform=Platform.CODEFORCES,
        takeaways=["lesson"],
        created_at=_FIXED_CREATED,
        updated_at=_FIXED_UPDATED,
    )
    items = [algo, pattern, mistake, problem, contest]
    graph = GraphBuilder(items).build()
    compiler = KnowledgeCompiler(graph)

    for item in items:
        first = compiler.compile(item)
        second = compiler.compile(item)
        assert dump_page(first.page) == dump_page(second.page), item.kind
