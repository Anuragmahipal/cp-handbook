"""Tests for handbook.learning.serialization."""

from __future__ import annotations

import json

import pytest

from handbook.learning.examples import build_example_page
from handbook.learning.exceptions import SchemaVersionError
from handbook.learning.page import Page, PageMetadata, Section
from handbook.learning.path import LearningPath
from handbook.learning.richtext import RichText
from handbook.learning.serialization import (
    dump_learning_path,
    dump_page,
    load_learning_path,
    load_page,
)


def test_page_round_trips_through_json():
    page = build_example_page()
    reloaded = load_page(dump_page(page))
    assert reloaded == page


def test_dumped_page_is_self_describing_json():
    page = Page(metadata=PageMetadata(title="X"))
    payload = json.loads(dump_page(page))
    assert payload["schema_version"] == 1
    assert payload["metadata"]["title"] == "X"


def test_load_page_rejects_missing_schema_version():
    page = Page(metadata=PageMetadata(title="X"))
    payload = json.loads(dump_page(page))
    del payload["schema_version"]
    with pytest.raises(SchemaVersionError):
        load_page(json.dumps(payload))


def test_load_page_rejects_a_newer_schema_version():
    page = Page(metadata=PageMetadata(title="X"))
    payload = json.loads(dump_page(page))
    payload["schema_version"] = 999
    with pytest.raises(SchemaVersionError):
        load_page(json.dumps(payload))


def test_learning_path_round_trips_through_json():
    path = LearningPath(title="A path")
    reloaded = load_learning_path(dump_learning_path(path))
    assert reloaded == path


def test_nested_blocks_and_diagrams_survive_the_round_trip():
    page = build_example_page()
    reloaded = load_page(dump_page(page))
    walkthrough = next(
        s for s in reloaded.sections if s.heading.as_plain_text() == "Walkthrough"
    )
    diagram = next(b for b in walkthrough.blocks if b.block_type == "diagram")
    assert len(diagram.elements) > 0
    assert len(diagram.arrows) > 0


def test_section_revision_history_survives_the_round_trip():
    original = Section(heading=RichText.plain("Original"))
    revised = original.revise(heading=RichText.plain("Revised"))
    page = Page(metadata=PageMetadata(title="X"), sections=(revised,))
    reloaded = load_page(dump_page(page))
    assert reloaded.sections[0].revision_of == original.id
    assert reloaded.sections[0].version == 2
