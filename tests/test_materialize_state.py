"""Tests for handbook.materialize.state.MaterializeState."""

from __future__ import annotations

from pathlib import Path

from handbook.materialize import MaterializeState
from handbook.models import Algorithm


def test_unknown_slug_returns_none(vault_root: Path):
    state = MaterializeState(vault_root)
    assert state.get("binary-search") is None
    assert state.has("binary-search") is False


def test_remember_and_get_round_trips(vault_root: Path):
    state = MaterializeState(vault_root)
    item = Algorithm(title="Binary Search", notes="auto-materialized")

    state.remember("binary-search", item)

    assert state.has("binary-search") is True
    reloaded = state.get("binary-search")
    assert reloaded.id == item.id
    assert reloaded.title == item.title
    assert isinstance(reloaded, Algorithm)


def test_state_persists_to_disk_across_instances(vault_root: Path):
    item = Algorithm(title="Binary Search")
    state = MaterializeState(vault_root)
    state.remember("binary-search", item)
    state.save()

    reloaded_state = MaterializeState(vault_root)
    reloaded = reloaded_state.get("binary-search")
    assert reloaded is not None
    assert reloaded.id == item.id

    assert (vault_root / ".handbook" / "materialize" / "state.json").exists()


def test_known_items_returns_every_remembered_item(vault_root: Path):
    state = MaterializeState(vault_root)
    state.remember("binary-search", Algorithm(title="Binary Search"))
    state.remember("two-pointers", Algorithm(title="Two Pointers"))

    items = state.known_items()

    assert {item.title for item in items} == {"Binary Search", "Two Pointers"}
