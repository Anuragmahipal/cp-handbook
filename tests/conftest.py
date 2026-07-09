from pathlib import Path

import pytest

from handbook import Handbook


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """A vault root that does not exist yet, to exercise nested creation."""
    return tmp_path / "vault"


@pytest.fixture
def hb(vault_root: Path) -> Handbook:
    return Handbook(root=vault_root)
