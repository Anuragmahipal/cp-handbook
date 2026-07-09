"""High-level tests for Handbook.store() and its convenience wrappers."""

from __future__ import annotations

from pathlib import Path

import pytest

from handbook import Handbook
from handbook.exceptions import DuplicateItemError, InvalidItemError
from handbook.models import Algorithm, Mistake, Pattern, Problem


def test_store_algorithm_writes_a_markdown_file(hb: Handbook, vault_root: Path):
    path = hb.store(Algorithm(title="Binary Exponentiation"))

    assert path == vault_root / "Algorithms" / "binary-exponentiation.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Binary Exponentiation" in content


def test_create_algorithm_delegates_to_store(hb: Handbook, vault_root: Path):
    path = hb.create_algorithm("Segment Tree")

    assert path == vault_root / "Algorithms" / "segment-tree.md"
    assert path.read_text(encoding="utf-8")


def test_nested_vault_is_created_automatically(vault_root: Path):
    assert not vault_root.exists()

    hb = Handbook(root=vault_root)
    path = hb.store(Algorithm(title="Fenwick Tree"))

    assert vault_root.exists()
    assert path.exists()


def test_each_knowledge_type_lands_in_its_own_folder(hb: Handbook, vault_root: Path):
    algo_path = hb.store(Algorithm(title="DSU"))
    problem_path = hb.store(
        Problem(title="Two Sum", platform="LeetCode", contest="Easy", index="1")
    )
    pattern_path = hb.store(Pattern(title="Sliding Window"))
    mistake_path = hb.store(Mistake(title="Off by one"))

    assert algo_path.parent == vault_root / "Algorithms"
    assert problem_path.parent == vault_root / "Problems"
    assert pattern_path.parent == vault_root / "Patterns"
    assert mistake_path.parent == vault_root / "Mistakes"
    for p in (algo_path, problem_path, pattern_path, mistake_path):
        assert p.exists()


def test_unicode_title_is_stored_without_error(hb: Handbook, vault_root: Path):
    path = hb.store(Algorithm(title="Быстрое возведение в степень"))

    assert path.exists()
    assert path.parent == vault_root / "Algorithms"
    # Content still carries the original, untransliterated title.
    assert "Быстрое возведение в степень" in path.read_text(encoding="utf-8")


def test_storing_same_id_twice_updates_in_place(hb: Handbook, vault_root: Path):
    item = Algorithm(title="KMP")

    first_path = hb.store(item)
    second_path = hb.store(item)

    assert first_path == second_path
    assert len(list((vault_root / "Algorithms").glob("*.md"))) == 1


def _extract_field(content: str, field: str) -> str:
    for line in content.splitlines():
        if line.startswith(f'{field}: "'):
            return line.split('"')[1]
    raise AssertionError(f"field {field!r} not found in rendered content")


def test_updating_by_id_preserves_created_at_and_bumps_updated_at(hb: Handbook):
    item = Algorithm(title="Z Function")
    path = hb.store(item)
    first_content = path.read_text(encoding="utf-8")
    first_created = _extract_field(first_content, "created")
    first_updated = _extract_field(first_content, "updated")

    revised = item.model_copy(update={"tags": ["updated-tag"]})
    hb.store(revised)
    second_content = path.read_text(encoding="utf-8")
    second_created = _extract_field(second_content, "created")
    second_updated = _extract_field(second_content, "updated")

    assert second_created == first_created
    assert second_updated != first_updated
    assert "updated-tag" in second_content


def test_overwrite_policy_rejects_by_default(hb: Handbook):
    hb.store(Algorithm(title="Dijkstra"))

    with pytest.raises(DuplicateItemError):
        hb.store(Algorithm(title="Dijkstra"))  # different id, same slug


def test_overwrite_true_replaces_existing_file(hb: Handbook, vault_root: Path):
    first = Algorithm(title="Prim's Algorithm", tags=["v1"])
    hb.store(first)

    second = Algorithm(title="Prim's Algorithm", tags=["v2"])
    path = hb.store(second, overwrite=True)

    assert path == vault_root / "Algorithms" / "prim-s-algorithm.md"
    assert len(list((vault_root / "Algorithms").glob("*.md"))) == 1
    content = path.read_text(encoding="utf-8")
    assert second.id in content
    assert first.id not in content
    assert "v2" in content and "v1" not in content


def test_store_rejects_non_knowledge_item(hb: Handbook):
    with pytest.raises(InvalidItemError):
        hb.store({"title": "not a model"})  # type: ignore[arg-type]

    with pytest.raises(InvalidItemError):
        hb.store("just a string")  # type: ignore[arg-type]


def test_renaming_item_relocates_and_removes_stale_file(hb: Handbook, vault_root: Path):
    item = Algorithm(title="Merge Sort")
    old_path = hb.store(item)

    renamed = item.model_copy(update={"title": "Merge Sort (Iterative)"})
    new_path = hb.store(renamed)

    assert new_path != old_path
    assert new_path.exists()
    assert not old_path.exists()
