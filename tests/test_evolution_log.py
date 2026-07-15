"""Tests for handbook.evolution.log.EvolutionLog."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from handbook.evolution.events import EventKind, KnowledgeGrowth, LearningEvent, MasteryChange
from handbook.evolution.log import EvolutionLog
from handbook.learning.enums import ReviewStatus


def _event(event_id: str, item_id: str = "p1", when: datetime = datetime(2026, 1, 1)) -> LearningEvent:
    return LearningEvent(id=event_id, kind=EventKind.SOLVED, item_id=item_id, when=when, summary="x")


def test_append_writes_a_new_event(vault_root: Path):
    log = EvolutionLog(vault_root)
    assert log.append(_event("e1")) is True
    assert log.has("e1")
    assert len(log.events()) == 1


def test_append_is_idempotent_for_the_same_id(vault_root: Path):
    log = EvolutionLog(vault_root)
    log.append(_event("e1"))
    result = log.append(_event("e1"))
    assert result is False
    assert len(log.events()) == 1


def test_events_persist_to_disk_across_instances(vault_root: Path):
    log = EvolutionLog(vault_root)
    log.append(_event("e1"))

    reloaded = EvolutionLog(vault_root)
    assert reloaded.has("e1")
    assert len(reloaded.events()) == 1

    assert (vault_root / ".handbook" / "evolution" / "events.jsonl").exists()


def test_append_only_never_rewrites_earlier_lines(vault_root: Path):
    log = EvolutionLog(vault_root)
    log.append(_event("e1"))
    path = vault_root / ".handbook" / "evolution" / "events.jsonl"
    first_line = path.read_text(encoding="utf-8").splitlines()[0]

    log.append(_event("e2"))
    lines_after = path.read_text(encoding="utf-8").splitlines()

    assert lines_after[0] == first_line  # untouched
    assert len(lines_after) == 2


def test_timeline_entries_are_sorted_chronologically(vault_root: Path):
    log = EvolutionLog(vault_root)
    log.append(_event("e-later", when=datetime(2026, 3, 1)))
    log.append(_event("e-earlier", when=datetime(2026, 1, 1)))
    log.append(_event("e-middle", when=datetime(2026, 2, 1)))

    entries = log.timeline_entries()

    assert [e.when for e in entries] == sorted(e.when for e in entries)


def test_timeline_entries_can_be_filtered_by_item(vault_root: Path):
    log = EvolutionLog(vault_root)
    log.append(_event("e1", item_id="algo-a"))
    log.append(_event("e2", item_id="algo-b"))

    entries = log.timeline_entries(item_id="algo-a")

    assert len(entries) == 1
    assert entries[0].item_id == "algo-a"


def test_latest_total_for_returns_zero_when_nothing_recorded(vault_root: Path):
    log = EvolutionLog(vault_root)
    assert log.latest_total_for("algo-a") == 0


def test_latest_total_for_returns_the_most_recent_growth(vault_root: Path):
    log = EvolutionLog(vault_root)
    log.append(
        KnowledgeGrowth(
            id="g1", item_id="algo-a", when=datetime(2026, 1, 1), summary="x",
            previous_total=0, new_total=2,
        )
    )
    log.append(
        KnowledgeGrowth(
            id="g2", item_id="algo-a", when=datetime(2026, 2, 1), summary="x",
            previous_total=2, new_total=5,
        )
    )
    assert log.latest_total_for("algo-a") == 5


def test_latest_mastery_for_defaults_to_new(vault_root: Path):
    log = EvolutionLog(vault_root)
    assert log.latest_mastery_for("algo-a") == ReviewStatus.NEW


def test_latest_mastery_for_returns_the_most_recent_change(vault_root: Path):
    log = EvolutionLog(vault_root)
    log.append(
        MasteryChange(
            id="m1", item_id="algo-a", when=datetime(2026, 1, 1), summary="x",
            previous_status=ReviewStatus.NEW, new_status=ReviewStatus.LEARNING,
        )
    )
    log.append(
        MasteryChange(
            id="m2", item_id="algo-a", when=datetime(2026, 2, 1), summary="x",
            previous_status=ReviewStatus.LEARNING, new_status=ReviewStatus.DUE,
        )
    )
    assert log.latest_mastery_for("algo-a") == ReviewStatus.DUE
