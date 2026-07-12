"""Golden (snapshot) tests for the notebook renderer.

Renders a fixed set of pages -- the worked example from
``handbook.learning.examples`` plus the four fixtures in ``examples/``
-- and compares the output byte-for-byte against a committed golden
file in ``tests/golden_notebook/``. A mismatch means the renderer's
output changed; either that change was unintentional (a regression --
fix the renderer) or intentional (a deliberate visual change --
regenerate the golden file).

To regenerate after an intentional change::

    UPDATE_NOTEBOOK_GOLDEN=1 pytest tests/test_notebook_golden.py

Regenerating silently turns a would-be failure into a pass, so it's
opt-in via an explicit environment variable rather than a flag that's
easy to leave on by accident.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from handbook.learning.examples import build_example_page
from handbook.learning.page import Page
from handbook.learning.serialization import load_page
from handbook.renderers.notebook import NotebookRenderer

_GOLDEN_DIR = Path(__file__).parent / "golden_notebook"
_EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
_UPDATE = os.environ.get("UPDATE_NOTEBOOK_GOLDEN") == "1"


def _load_example_pages() -> dict[str, Page]:
    pages = {"binary_search_pattern": build_example_page()}
    for json_file in sorted(_EXAMPLES_DIR.glob("*.json")):
        pages[json_file.stem] = load_page(json_file.read_text(encoding="utf-8"))
    return pages


_PAGES = _load_example_pages()


@pytest.mark.parametrize("name", sorted(_PAGES))
def test_rendered_html_matches_golden_snapshot(name: str):
    page = _PAGES[name]
    result = NotebookRenderer().render(page)
    golden_path = _GOLDEN_DIR / f"{name}.html"

    if _UPDATE or not golden_path.exists():
        _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(result.html, encoding="utf-8")
        if not _UPDATE:
            pytest.fail(
                f"No golden file existed for {name!r}; one was just "
                "created. Re-run the tests to verify against it."
            )
        return

    expected = golden_path.read_text(encoding="utf-8")
    assert result.html == expected, (
        f"Rendered output for {name!r} no longer matches "
        f"{golden_path}. If this is intentional, regenerate with "
        "UPDATE_NOTEBOOK_GOLDEN=1."
    )
