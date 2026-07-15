"""Tests for handbook.evolution.events."""

from __future__ import annotations

from datetime import datetime

from handbook.evolution.events import (
    EventKind,
    KnowledgeGrowth,
    LearningEvent,
    MasteryChange,
    TimelineEntry,
)
from handbook.learning.enums import ReviewStatus


def test_learning_event_round_trips_through_json():
    event = LearningEvent(
        id="abc", kind=EventKind.SOLVED, item_id="p1", when=datetime(2026, 1, 1), summary="Solved X"
    )
    data = event.model_dump(mode="json")
    reloaded = LearningEvent.model_validate(data)
    assert reloaded == event


def test_knowledge_growth_carries_before_and_after():
    event = KnowledgeGrowth(
        id="g1",
        item_id="algo1",
        when=datetime(2026, 1, 1),
        summary="grew",
        previous_total=2,
        new_total=3,
    )
    assert event.kind == EventKind.KNOWLEDGE_GROWTH
    assert event.new_total - event.previous_total == 1


def test_mastery_change_carries_status_transition():
    event = MasteryChange(
        id="m1",
        item_id="algo1",
        when=datetime(2026, 1, 1),
        summary="advanced",
        previous_status=ReviewStatus.NEW,
        new_status=ReviewStatus.LEARNING,
    )
    assert event.previous_status != event.new_status


def test_timeline_entry_from_event_carries_only_display_fields():
    event = KnowledgeGrowth(
        id="g1",
        item_id="algo1",
        when=datetime(2026, 1, 1),
        summary="Binary Search: now used by 3 problems (+1)",
        previous_total=2,
        new_total=3,
    )
    entry = TimelineEntry.from_event(event)
    assert entry.when == event.when
    assert entry.item_id == event.item_id
    assert entry.label == event.summary
    assert not hasattr(entry, "new_total")
