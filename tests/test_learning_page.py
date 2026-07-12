"""Tests for handbook.learning.page: PageMetadata, Section, Page."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from handbook.learning.blocks import TextBlock
from handbook.learning.enums import AnchorType
from handbook.learning.page import Page, PageMetadata, Section
from handbook.learning.review import MemoryAnchor, ReviewCue
from handbook.learning.richtext import RichText


def test_page_metadata_rejects_blank_title():
    with pytest.raises(ValidationError):
        PageMetadata(title="   ")


def test_page_metadata_tags_are_normalized():
    metadata = PageMetadata(title="X", tags=["DP", " dp ", "Greedy"])
    assert metadata.tags == ("dp", "greedy")


def test_section_rejects_duplicate_block_ids():
    block = TextBlock(id="dup", content=RichText.plain("a"))
    other = TextBlock(id="dup", content=RichText.plain("b"))
    with pytest.raises(ValidationError):
        Section(heading=RichText.plain("H"), blocks=(block, other))


def test_memory_anchor_may_target_the_section_itself():
    anchor = MemoryAnchor(
        target_id="will-be-the-section-id",
        prompt=RichText.plain("What's this section about?"),
        anchor_type=AnchorType.QUESTION,
    )
    section = Section(
        id="will-be-the-section-id",
        heading=RichText.plain("H"),
        memory_anchors=(anchor,),
    )
    assert section.memory_anchors[0].target_id == section.id


def test_memory_anchor_targeting_unknown_id_is_rejected():
    anchor = MemoryAnchor(
        target_id="does-not-exist",
        prompt=RichText.plain("cue"),
    )
    with pytest.raises(ValidationError):
        Section(heading=RichText.plain("H"), memory_anchors=(anchor,))


def test_review_cue_must_reference_a_known_anchor():
    with pytest.raises(ValidationError):
        Section(
            heading=RichText.plain("H"),
            review_cues=(ReviewCue(anchor_id="unknown-anchor"),),
        )


def test_review_cue_referencing_a_real_anchor_is_accepted():
    block = TextBlock(id="b1", content=RichText.plain("content"))
    anchor = MemoryAnchor(target_id="b1", prompt=RichText.plain("cue"))
    section = Section(
        heading=RichText.plain("H"),
        blocks=(block,),
        memory_anchors=(anchor,),
        review_cues=(ReviewCue(anchor_id=anchor.id),),
    )
    assert section.review_cues[0].anchor_id == anchor.id


def test_page_rejects_duplicate_section_ids():
    section = Section(id="dup", heading=RichText.plain("H"))
    other = Section(id="dup", heading=RichText.plain("H2"))
    with pytest.raises(ValidationError):
        Page(metadata=PageMetadata(title="X"), sections=(section, other))


def test_page_accepts_distinct_sections_in_reading_order():
    first = Section(heading=RichText.plain("First"))
    second = Section(heading=RichText.plain("Second"))
    page = Page(metadata=PageMetadata(title="X"), sections=(first, second))
    assert [s.heading.as_plain_text() for s in page.sections] == ["First", "Second"]
