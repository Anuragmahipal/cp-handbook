"""Tests for handbook.learning.versioning: LIRModel, Identified,
Revisable, supersede."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from handbook.learning.page import Section
from handbook.learning.richtext import RichText
from handbook.learning.versioning import supersede


def _section(**overrides: object) -> Section:
    defaults: dict[object, object] = {"heading": RichText.plain("Heading")}
    defaults.update(overrides)
    return Section(**defaults)


def test_stable_id_is_generated_by_default():
    section = _section()
    assert section.id


def test_explicit_id_is_preserved():
    section = _section(id="my-stable-id")
    assert section.id == "my-stable-id"


def test_models_are_frozen():
    section = _section()
    with pytest.raises(ValidationError):
        section.heading = RichText.plain("New heading")  # type: ignore[misc]


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        Section(heading=RichText.plain("H"), not_a_real_field="oops")  # type: ignore[call-arg]


def test_new_object_starts_at_version_one():
    section = _section()
    assert section.version == 1
    assert section.revision_of is None
    assert section.superseded_by is None


def test_revise_produces_a_new_object_with_linked_history():
    original = _section()
    revised = original.revise(heading=RichText.plain("New heading"))

    assert revised.id != original.id
    assert revised.version == original.version + 1
    assert revised.revision_of == original.id
    assert revised.heading.as_plain_text() == "New heading"
    # original is untouched -- it's frozen, revise() cannot have mutated it
    assert original.version == 1
    assert original.heading.as_plain_text() == "Heading"


def test_revise_resets_superseded_by_even_if_original_had_one():
    original = _section()
    once_revised = original.revise()
    twice_revised = once_revised.revise()
    assert twice_revised.superseded_by is None


def test_supersede_flags_a_copy_of_the_original_without_mutating_it():
    original = _section()
    revised = original.revise(heading=RichText.plain("New heading"))

    flagged_original = supersede(original, revised)

    assert flagged_original.superseded_by == revised.id
    assert flagged_original.id == original.id  # same identity, just flagged
    # the original reference itself is never mutated
    assert original.superseded_by is None
