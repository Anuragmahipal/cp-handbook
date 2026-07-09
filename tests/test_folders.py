"""Tests for folder resolution."""

from __future__ import annotations

import pytest

from handbook.core.folders import resolve_folder
from handbook.exceptions import StorageError
from handbook.models import Algorithm, KnowledgeItem, Mistake, Pattern, Problem


@pytest.mark.parametrize(
    ("item", "expected_folder"),
    [
        (Algorithm(title="X"), "Algorithms"),
        (Problem(title="X", platform="CF", contest="123", index="A"), "Problems"),
        (Pattern(title="X"), "Patterns"),
        (Mistake(title="X"), "Mistakes"),
    ],
)
def test_known_types_resolve_to_their_folder(item: KnowledgeItem, expected_folder: str):
    assert resolve_folder(item) == expected_folder


def test_unregistered_type_raises_storage_error():
    class Unregistered(KnowledgeItem):
        pass

    with pytest.raises(StorageError):
        resolve_folder(Unregistered(title="X"))
