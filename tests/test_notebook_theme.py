"""Tests for handbook.renderers.notebook.theme."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from handbook.learning.enums import CalloutKind, ReviewStatus
from handbook.renderers.notebook.theme import NotebookTheme

_PRESETS = [
    NotebookTheme.light_notebook,
    NotebookTheme.dark_notebook,
    NotebookTheme.handwritten,
]


@pytest.mark.parametrize("preset", _PRESETS)
def test_every_preset_covers_every_callout_kind(preset):
    theme = preset()
    for kind in CalloutKind:
        assert kind.value in theme.callout_colors


@pytest.mark.parametrize("preset", _PRESETS)
def test_every_preset_covers_every_review_status(preset):
    theme = preset()
    for status in ReviewStatus:
        assert status.value in theme.review_colors


def test_theme_is_frozen():
    theme = NotebookTheme.light_notebook()
    with pytest.raises(ValidationError):
        theme.accent = "#000000"  # type: ignore[misc]


def test_theme_rejects_missing_callout_color():
    with pytest.raises(ValidationError):
        NotebookTheme(
            name="Incomplete",
            page_background="#fff",
            card_background="#fff",
            card_border="#ccc",
            ink="#000",
            ink_muted="#666",
            accent="#f00",
            heading_font="serif",
            body_font="serif",
            code_font="monospace",
            callout_colors={},  # missing every kind
            review_colors={status.value: "#000" for status in ReviewStatus},
            syntax_colors={
                "keyword": "#000",
                "string": "#000",
                "comment": "#000",
                "number": "#000",
                "preprocessor": "#000",
            },
            diagram_node_fill="#fff",
            diagram_node_stroke="#000",
            diagram_edge_stroke="#000",
            diagram_emphasis_stroke="#000",
        )


def test_presets_are_visually_distinct():
    light = NotebookTheme.light_notebook()
    dark = NotebookTheme.dark_notebook()
    handwritten = NotebookTheme.handwritten()
    assert light.page_background != dark.page_background
    assert light.heading_font != handwritten.heading_font
