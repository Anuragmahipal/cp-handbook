"""Unit tests for handbook.renderers.filters -- the reusable rendering
helpers registered as Jinja filters (deliverable: "reusable rendering
helpers" / "renderer utilities"). Tested directly, independent of any
template, since they're plain functions with no Jinja/model dependency.
"""

from __future__ import annotations

from handbook.renderers import filters


def test_blockquote_prefixes_every_line():
    assert filters.blockquote("one\ntwo") == "> one\n> two\n"


def test_blockquote_uses_bare_gt_for_blank_lines():
    """A blank line inside an Obsidian callout must still start with
    '>' (even with nothing after it) or the callout ends early."""
    result = filters.blockquote("one\n\ntwo")
    assert result == "> one\n>\n> two\n"


def test_blockquote_strips_leading_and_trailing_blank_lines():
    assert filters.blockquote("\n\none\n\n") == "> one\n"


def test_blockquote_keeps_a_single_trailing_newline():
    """Required so that a blank source line between two adjacent
    `{% filter blockquote %}` blocks in a template produces a real
    blank-line separator in the rendered output -- see
    templates/algorithms/algorithm.md.j2 and friends."""
    assert filters.blockquote("x").endswith("\n")
    assert not filters.blockquote("x").endswith("\n\n")


def test_editable_block_uses_value_when_present():
    result = filters.editable_block("Real content.", "intuition", "placeholder")

    assert result == (
        "<!-- ai:intuition:start -->\nReal content.\n<!-- ai:intuition:end -->"
    )


def test_editable_block_falls_back_to_placeholder_when_empty():
    for empty in ("", "   ", None):
        result = filters.editable_block(empty, "cause", "Describe the mistake.")
        assert "Describe the mistake." in result
        assert "<!-- ai:cause:start -->" in result
        assert "<!-- ai:cause:end -->" in result


def test_editable_block_markers_are_correctly_ordered():
    result = filters.editable_block("body", "notes", "placeholder")
    start = result.index("<!-- ai:notes:start -->")
    body = result.index("body")
    end = result.index("<!-- ai:notes:end -->")
    assert start < body < end


def test_mermaid_escape_handles_quotes_and_newlines():
    assert filters.mermaid_escape('Say "hi"') == "Say &quot;hi&quot;"
    assert filters.mermaid_escape("line1\nline2") == "line1 line2"


def test_status_emoji_known_and_unknown():
    assert filters.status_emoji("Active") == "🟢"
    assert filters.status_emoji("Mastered") == "⭐"
    assert filters.status_emoji("not-a-real-status") == "🔹"


def test_difficulty_emoji_known_and_none():
    assert filters.difficulty_emoji("Hard") == "🟠"
    assert filters.difficulty_emoji(None) == ""
    assert filters.difficulty_emoji("") == ""


def test_platform_emoji_known_and_unknown():
    assert filters.platform_emoji("Codeforces") == "🟦"
    assert filters.platform_emoji("not-a-real-platform") == "🔹"


def test_format_dt_renders_short_human_date():
    assert filters.format_dt("2026-07-10T14:35:00") == "Jul 10, 2026"


def test_format_dt_returns_input_unchanged_on_bad_input():
    """Documents the contract: format_dt does not raise on bad input,
    it just echoes it back -- callers with an Optional[str] field (like
    Contest.start_time) must guard for None/empty themselves rather
    than relying on this filter to produce a friendly placeholder."""
    assert filters.format_dt("not-a-date") == "not-a-date"


def test_format_minutes_various():
    assert filters.format_minutes(None) == "—"
    assert filters.format_minutes(0) == "0m"
    assert filters.format_minutes(45) == "45m"
    assert filters.format_minutes(60) == "1h"
    assert filters.format_minutes(95) == "1h 35m"
