"""Tests for handbook.renderers.notebook.blocks_html."""

from __future__ import annotations

from handbook.learning.blocks import (
    Callout,
    CodeAnnotation,
    CodeBlock,
    TextBlock,
    VisualBlock,
)
from handbook.learning.enums import (
    AnchorType,
    CalloutKind,
    ElementRole,
    Emphasis,
    ReviewStatus,
)
from handbook.learning.review import MemoryAnchor, ReviewCue
from handbook.learning.richtext import RichText, Span
from handbook.renderers.notebook.blocks_html import (
    render_block,
    render_callout,
    render_code_block,
    render_memory_anchor,
    render_review_badge,
    render_rich_text,
    render_text_block,
    render_visual_chip,
)
from handbook.renderers.notebook.svg import SVGRenderer
from handbook.renderers.notebook.theme import NotebookTheme


def _svg_renderer() -> SVGRenderer:
    return SVGRenderer(NotebookTheme.light_notebook())


def test_render_rich_text_wraps_strong_span():
    rt = RichText(spans=(Span(text="hi", emphasis=(Emphasis.STRONG,)),))
    assert render_rich_text(rt) == "<strong>hi</strong>"


def test_render_rich_text_nests_multiple_emphases():
    rt = RichText(
        spans=(Span(text="hi", emphasis=(Emphasis.STRONG, Emphasis.EMPHASIS)),)
    )
    html = render_rich_text(rt)
    assert html == "<strong><em>hi</em></strong>"


def test_render_rich_text_escapes_html():
    rt = RichText.plain("a < b & c")
    assert render_rich_text(rt) == "a &lt; b &amp; c"


def test_render_rich_text_link_target_is_not_a_navigable_anchor():
    rt = RichText(spans=(Span(text="see this", link_target="other-page"),))
    html = render_rich_text(rt)
    assert "<a " not in html
    assert 'class="lir-link"' in html
    assert 'title="other-page"' in html


def test_render_text_block_includes_role_class():
    block = TextBlock(content=RichText.plain("hello"))
    html = render_text_block(block)
    assert 'class="lir-text lir-text-body"' in html


def test_render_code_block_has_one_row_per_line():
    block = CodeBlock(language="python", source="a = 1\nb = 2\nc = 3")
    html = render_code_block(block)
    assert html.count('class="lir-code-row') == 3


def test_render_code_block_highlights_specified_lines():
    block = CodeBlock(language="python", source="a = 1\nb = 2", highlighted_lines=(2,))
    html = render_code_block(block)
    assert "lir-code-row-highlighted" in html


def test_render_code_block_places_annotation_on_correct_line():
    block = CodeBlock(
        language="python",
        source="a = 1\nb = 2",
        annotations=(CodeAnnotation(line=2, note="watch this"),),
    )
    html = render_code_block(block)
    rows = html.split("<tr")
    assert "watch this" not in rows[1]
    assert "watch this" in rows[2]


def test_render_visual_chip_standalone():
    block = VisualBlock(role=ElementRole.VALUE, label=RichText.plain("n"), value="7")
    html = render_visual_chip(block)
    assert "lir-role-value" in html
    assert ">7<" in html


def test_render_callout_uses_kind_class_and_renders_body():
    callout = Callout(
        kind=CalloutKind.WARNING,
        title="Careful",
        body=(TextBlock(content=RichText.plain("watch out")),),
    )
    html = render_callout(callout, _svg_renderer())
    assert "lir-callout-warning" in html
    assert "Careful" in html
    assert "watch out" in html


def test_render_memory_anchor_shows_prompt_not_answer():
    anchor = MemoryAnchor(
        target_id="somewhere",
        prompt=RichText.plain("why does this work?"),
        anchor_type=AnchorType.QUESTION,
    )
    html = render_memory_anchor(anchor)
    assert "why does this work?" in html
    assert 'data-anchor-type="question"' in html


def test_render_review_badge_shows_status():
    cue = ReviewCue(anchor_id="a", status=ReviewStatus.DUE)
    html = render_review_badge(cue)
    assert "lir-review-due" in html
    assert "DUE" in html


def test_render_block_dispatches_by_block_type():
    text = TextBlock(content=RichText.plain("hi"))
    chip = VisualBlock(role=ElementRole.NODE, label=RichText.plain("n"))
    assert render_block(text, _svg_renderer()) == render_text_block(text)
    assert render_block(chip, _svg_renderer()) == render_visual_chip(chip)
