"""Tests for handbook.learning.path: LearningPath, PathStep."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from handbook.learning.path import LearningPath, PathStep


def test_learning_path_rejects_blank_title():
    with pytest.raises(ValidationError):
        LearningPath(title="  ")


def test_learning_path_order_follows_step_list_position():
    path = LearningPath(
        title="Graphs from scratch",
        steps=(
            PathStep(page_id="page-1"),
            PathStep(page_id="page-2", section_id="section-2a"),
            PathStep(page_id="page-3", optional=True),
        ),
    )
    assert [step.page_id for step in path.steps] == ["page-1", "page-2", "page-3"]
    assert path.steps[1].section_id == "section-2a"
    assert path.steps[2].optional is True


def test_learning_path_rejects_duplicate_step_ids():
    step = PathStep(id="dup", page_id="page-1")
    other = PathStep(id="dup", page_id="page-2")
    with pytest.raises(ValidationError):
        LearningPath(title="X", steps=(step, other))


def test_learning_path_is_revisable():
    path = LearningPath(title="Original")
    revised = path.revise(title="Reordered")
    assert revised.version == 2
    assert revised.revision_of == path.id
    assert revised.title == "Reordered"
