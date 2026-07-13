"""Golden (snapshot) tests for compiled-and-rendered notebook pages.

Mirrors ``tests/test_notebook_golden.py``'s pattern exactly, one layer
further up the pipeline: instead of hand-authored ``Page`` fixtures,
these start from ``KnowledgeItem`` instances, run them through
``KnowledgeCompiler``, and render the result -- a fixed, small,
interconnected knowledge base with explicit ids/timestamps so the
output is byte-identical across runs and across processes (see
``tests/test_compiler_determinism.py`` for why that's true by
construction, not by luck).

To regenerate after an intentional change to a compiler or the
renderer::

    UPDATE_COMPILER_GOLDEN=1 pytest tests/test_compiler_golden.py
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from handbook.graph import GraphBuilder
from handbook.learning.compiler import KnowledgeCompiler
from handbook.models import Algorithm, Contest, ContestType, Mistake, Pattern, Platform, Problem
from handbook.renderers.notebook import NotebookRenderer

_GOLDEN_DIR = Path(__file__).parent / "golden_compiled_notebook"
_UPDATE = os.environ.get("UPDATE_COMPILER_GOLDEN") == "1"

_T = datetime(2026, 3, 15, 8, 0, 0)


def _fixed_vault() -> dict[str, object]:
    algo = Algorithm(
        id="a0000000-0000-0000-0000-000000000001",
        title="Binary Lifting",
        category="Tree",
        intuition=(
            "Precompute 2^k-th ancestors so any ancestor query answers in "
            "O(log n) instead of O(n)."
        ),
        implementation=(
            "for (int k = 1; k < LOG; k++)\n"
            "    for (int v = 1; v <= n; v++)\n"
            "        up[k][v] = up[k - 1][up[k - 1][v]];"
        ),
        time_complexity="O(n log n) preprocessing, O(log n) per query",
        space_complexity="O(n log n)",
        pitfalls=["Off-by-one in the LOG bound", "Forgetting to precompute depth first"],
        related_problems=["Lowest Common Ancestor"],
        created_at=_T,
        updated_at=_T,
    )
    pattern = Pattern(
        id="a0000000-0000-0000-0000-000000000002",
        title="Ancestor Jumping",
        description="Answer ancestor/depth queries by jumping in powers of two.",
        recognition_cues=["k-th ancestor query", "LCA query"],
        related_algorithms=["Binary Lifting"],
        example_problems=["Lowest Common Ancestor"],
        created_at=_T,
        updated_at=_T,
    )
    mistake = Mistake(
        id="a0000000-0000-0000-0000-000000000003",
        title="LOG bound too small",
        cause="LOG was set to log2(n) instead of ceil(log2(n)) + 1.",
        prevention="Always compute LOG as (int)log2(MAXN) + 1, not from n itself.",
        related_algorithms=["Binary Lifting"],
        related_problems=["Lowest Common Ancestor"],
        created_at=_T,
        updated_at=_T,
    )
    problem = Problem(
        id="a0000000-0000-0000-0000-000000000004",
        title="Lowest Common Ancestor",
        platform=Platform.CODEFORCES,
        contest="1",
        index="A",
        rating=1900,
        algorithms=["Binary Lifting"],
        patterns=["Ancestor Jumping"],
        mistakes=["LOG bound too small"],
        attempts=2,
        created_at=_T,
        updated_at=_T,
    )
    contest = Contest(
        id="a0000000-0000-0000-0000-000000000005",
        title="Educational Codeforces Round 1",
        platform=Platform.CODEFORCES,
        contest_type=ContestType.EDUCATIONAL,
        problems=["Lowest Common Ancestor"],
        takeaways=["Tree problems reward precomputation over per-query recursion."],
        rank=450,
        rating_change=18,
        created_at=_T,
        updated_at=_T,
    )
    return {
        "algorithm": algo,
        "pattern": pattern,
        "mistake": mistake,
        "problem": problem,
        "contest": contest,
    }


_VAULT = _fixed_vault()
_GRAPH = GraphBuilder(list(_VAULT.values())).build()


@pytest.mark.parametrize("name", sorted(_VAULT))
def test_compiled_html_matches_golden_snapshot(name: str):
    item = _VAULT[name]
    result = KnowledgeCompiler(_GRAPH).compile(item)
    rendered = NotebookRenderer().render(result.page)
    golden_path = _GOLDEN_DIR / f"{name}.html"

    if _UPDATE or not golden_path.exists():
        _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(rendered.html, encoding="utf-8")
        if not _UPDATE:
            pytest.fail(
                f"No golden file existed for {name!r}; one was just "
                "created. Re-run the tests to verify against it."
            )
        return

    expected = golden_path.read_text(encoding="utf-8")
    assert rendered.html == expected, (
        f"Compiled+rendered output for {name!r} no longer matches "
        f"{golden_path}. If this is intentional, regenerate with "
        "UPDATE_COMPILER_GOLDEN=1."
    )
