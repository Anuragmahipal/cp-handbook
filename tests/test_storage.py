"""Tests for the storage engine and its index, independent of Handbook."""

from __future__ import annotations

from pathlib import Path

import pytest

from handbook.core.storage import StorageEngine
from handbook.exceptions import DuplicateItemError, StorageError
from handbook.models import Algorithm


def test_plan_then_commit_creates_directories_and_file(tmp_path: Path):
    root = tmp_path / "vault"
    engine = StorageEngine(root)
    item = Algorithm(title="Topological Sort")

    plan = engine.plan(item, folder_name="Algorithms", extension=".md", overwrite=False)
    assert not plan.absolute_path.exists()

    written = engine.commit(plan, "content")

    assert written == root / "Algorithms" / "topological-sort.md"
    assert written.read_text(encoding="utf-8") == "content"


def test_duplicate_slug_rejected_without_overwrite(tmp_path: Path):
    engine = StorageEngine(tmp_path / "vault")
    a = Algorithm(title="Kadane's Algorithm")
    b = Algorithm(title="Kadane's Algorithm")  # different id, same title

    plan_a = engine.plan(a, folder_name="Algorithms", extension=".md", overwrite=False)
    engine.commit(plan_a, "first")

    with pytest.raises(DuplicateItemError):
        engine.plan(b, folder_name="Algorithms", extension=".md", overwrite=False)


def test_duplicate_slug_allowed_with_overwrite(tmp_path: Path):
    root = tmp_path / "vault"
    engine = StorageEngine(root)
    a = Algorithm(title="Union Find")
    b = Algorithm(title="Union Find")

    plan_a = engine.plan(a, folder_name="Algorithms", extension=".md", overwrite=False)
    engine.commit(plan_a, "v1")
    plan_b = engine.plan(b, folder_name="Algorithms", extension=".md", overwrite=True)
    engine.commit(plan_b, "v2")

    path = root / "Algorithms" / "union-find.md"
    assert path.read_text(encoding="utf-8") == "v2"
    assert len(list((root / "Algorithms").glob("*.md"))) == 1


def test_same_id_is_treated_as_an_update(tmp_path: Path):
    root = tmp_path / "vault"
    engine = StorageEngine(root)
    item = Algorithm(title="Trie")

    plan1 = engine.plan(
        item, folder_name="Algorithms", extension=".md", overwrite=False
    )
    engine.commit(plan1, "v1")

    plan2 = engine.plan(
        item, folder_name="Algorithms", extension=".md", overwrite=False
    )
    assert plan2.is_update
    assert plan2.relative_path == plan1.relative_path
    engine.commit(plan2, "v2")

    assert len(list((root / "Algorithms").glob("*.md"))) == 1


def test_empty_slug_raises_storage_error(tmp_path: Path):
    engine = StorageEngine(tmp_path / "vault")
    item = Algorithm(title="!!!")  # transliterates to nothing usable

    with pytest.raises(StorageError):
        engine.plan(item, folder_name="Algorithms", extension=".md", overwrite=False)


def test_nested_vault_directories_are_created(tmp_path: Path):
    root = tmp_path / "a" / "b" / "c" / "vault"
    engine = StorageEngine(root)
    item = Algorithm(title="Dynamic Programming")

    plan = engine.plan(item, folder_name="Algorithms", extension=".md", overwrite=False)
    engine.commit(plan, "content")

    assert (root / "Algorithms" / "dynamic-programming.md").exists()


def test_index_survives_reload(tmp_path: Path):
    root = tmp_path / "vault"
    item = Algorithm(title="AVL Tree")

    engine1 = StorageEngine(root)
    engine1.commit(
        engine1.plan(item, folder_name="Algorithms", extension=".md", overwrite=False),
        "content",
    )

    # A fresh engine instance re-reads the persisted index from disk.
    engine2 = StorageEngine(root)
    plan = engine2.plan(
        item, folder_name="Algorithms", extension=".md", overwrite=False
    )
    assert plan.is_update
