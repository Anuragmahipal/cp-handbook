"""Tests for handbook.learning.examples."""

from __future__ import annotations

from handbook.learning.examples import build_example_page


def test_example_page_builds_without_error():
    page = build_example_page()
    assert page.metadata.title == "Binary Search on the Answer"
    assert len(page.sections) == 3


def test_example_page_diagram_has_valid_edges():
    walkthrough = build_example_page().sections[1]
    diagram = next(b for b in walkthrough.blocks if b.block_type == "diagram")
    element_ids = {element.id for element in diagram.elements}
    for arrow in diagram.arrows:
        assert arrow.from_id in element_ids
        assert arrow.to_id in element_ids


def test_example_page_review_cue_points_at_a_real_anchor():
    walkthrough = build_example_page().sections[1]
    anchor_ids = {anchor.id for anchor in walkthrough.memory_anchors}
    for cue in walkthrough.review_cues:
        assert cue.anchor_id in anchor_ids
