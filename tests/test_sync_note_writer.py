"""Tests for handbook.sync.note_writer: persisting a RevisionNote to disk."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from handbook.sync.note_writer import write_revision_note
from handbook.sync.revision_note import RevisionNote


def _note(**overrides) -> RevisionNote:
    defaults = dict(
        problem_id="abc-123",
        problem_title="Two Pointer Practice",
        platform="Codeforces",
        contest="1868",
        index="A",
        url="https://codeforces.com/contest/1868/problem/A",
        rating=1200,
        tags=["two pointers"],
        source="Contest",
        solved_at=datetime(2026, 1, 1, 12, 0),
    )
    defaults.update(overrides)
    return RevisionNote(**defaults)


def test_write_revision_note_creates_markdown_and_json(vault_root: Path):
    note = _note()

    written = write_revision_note(vault_root, note)

    assert written.markdown_path.exists()
    assert written.json_path.exists()


def test_markdown_path_uses_slugified_title(vault_root: Path):
    note = _note(problem_title="Two Pointer Practice!")

    written = write_revision_note(vault_root, note)

    assert written.markdown_path.name == "two-pointer-practice.md"
    assert written.markdown_path.parent.name == "Revision Notes"


def test_json_path_is_keyed_by_problem_id(vault_root: Path):
    note = _note(problem_id="my-problem-id")

    written = write_revision_note(vault_root, note)

    assert written.json_path.name == "my-problem-id.json"
    assert ".handbook" in written.json_path.parts


def test_json_content_round_trips(vault_root: Path):
    note = _note()

    written = write_revision_note(vault_root, note)
    data = json.loads(written.json_path.read_text(encoding="utf-8"))

    assert data["problem_id"] == "abc-123"
    assert data["problem_title"] == "Two Pointer Practice"
    assert data["rating"] == 1200


def test_markdown_contains_all_seven_sections(vault_root: Path):
    note = _note()

    written = write_revision_note(vault_root, note)
    markdown = written.markdown_path.read_text(encoding="utf-8")

    for heading in [
        "Problem",
        "Core Idea",
        "Recognition",
        "Mistake",
        "Complexity",
        "Key Observation",
        "Implementation Trick",
    ]:
        assert heading in markdown


def test_blank_sections_render_as_editable_placeholders(vault_root: Path):
    note = (
        _note()
    )  # core_idea/complexity/key_observation/implementation_trick all blank

    written = write_revision_note(vault_root, note)
    markdown = written.markdown_path.read_text(encoding="utf-8")

    assert "<!-- ai:core_idea:start -->" in markdown
    assert "Describe the core idea in 1-2 lines." in markdown
    assert "<!-- ai:complexity:start -->" in markdown
    assert "<!-- ai:key_observation:start -->" in markdown
    assert "<!-- ai:implementation_trick:start -->" in markdown


def test_filled_sections_render_the_actual_text(vault_root: Path):
    note = _note(core_idea="Two-pointer sweep from both ends.")

    written = write_revision_note(vault_root, note)
    markdown = written.markdown_path.read_text(encoding="utf-8")

    assert "Two-pointer sweep from both ends." in markdown


def test_rewriting_the_same_note_overwrites_rather_than_duplicates(vault_root: Path):
    note = _note()

    write_revision_note(vault_root, note)
    updated = _note(core_idea="Updated idea.")
    written_again = write_revision_note(vault_root, updated)

    markdown_files = list((vault_root / "Revision Notes").glob("*.md"))
    assert len(markdown_files) == 1
    assert "Updated idea." in written_again.markdown_path.read_text(encoding="utf-8")
