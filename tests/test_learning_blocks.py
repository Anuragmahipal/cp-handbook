"""Tests for handbook.learning.blocks."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from handbook.learning.blocks import (
    Arrow,
    Block,
    Callout,
    CodeAnnotation,
    CodeBlock,
    Connection,
    DiagramBlock,
    TextBlock,
    VisualBlock,
)
from handbook.learning.enums import CalloutKind, ElementRole
from handbook.learning.richtext import RichText

_BlockAdapter: TypeAdapter[Block] = TypeAdapter(Block)


def test_block_union_discriminates_by_block_type_from_a_plain_dict():
    payload = {"block_type": "text", "content": {"spans": [{"text": "hello"}]}}
    block = _BlockAdapter.validate_python(payload)
    assert isinstance(block, TextBlock)
    assert block.content.as_plain_text() == "hello"


def test_code_block_defaults_and_annotation_line_bounds():
    code = CodeBlock(language="cpp", source="a\nb\nc")
    assert code.highlighted_lines == ()
    assert code.annotations == ()

    with pytest.raises(ValidationError):
        CodeBlock(
            language="cpp",
            source="a\nb\nc",
            annotations=(CodeAnnotation(line=99, note="out of range"),),
        )


def test_diagram_block_rejects_arrow_to_unknown_element():
    known = VisualBlock(id="n1", role=ElementRole.NODE, label=RichText.plain("N1"))
    with pytest.raises(ValidationError):
        DiagramBlock(
            elements=(known,),
            arrows=(Arrow(from_id="n1", to_id="does-not-exist"),),
        )


def test_diagram_block_rejects_connection_to_unknown_element():
    known = VisualBlock(id="n1", role=ElementRole.NODE, label=RichText.plain("N1"))
    with pytest.raises(ValidationError):
        DiagramBlock(
            elements=(known,),
            connections=(Connection(from_id="does-not-exist", to_id="n1"),),
        )


def test_diagram_block_accepts_edges_between_known_elements():
    a = VisualBlock(id="a", role=ElementRole.NODE, label=RichText.plain("A"))
    b = VisualBlock(id="b", role=ElementRole.NODE, label=RichText.plain("B"))
    diagram = DiagramBlock(
        elements=(a, b),
        arrows=(Arrow(from_id="a", to_id="b", label="calls"),),
    )
    assert len(diagram.arrows) == 1


def test_visual_block_serves_as_both_standalone_block_and_diagram_element():
    standalone = VisualBlock(role=ElementRole.STATE, label=RichText.plain("visited"))
    assert standalone.block_type == "visual"

    element = VisualBlock(id="x", role=ElementRole.NODE, label=RichText.plain("X"))
    diagram = DiagramBlock(elements=(element,))
    assert diagram.elements[0] is element


def test_callout_body_is_limited_to_text_and_code_blocks():
    callout = Callout(
        kind=CalloutKind.PITFALL,
        title="Careful",
        body=(CodeBlock(language="python", source="x = 1"),),
    )
    assert callout.body[0].block_type == "code"
