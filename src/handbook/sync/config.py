"""Sync configuration: Codeforces handle + vault location.

Reads (and, unlike :class:`handbook.settings.Settings`, writes) the
*same* ``config/settings.toml`` file, with a ``[codeforces]`` section
added -- one physical config file for the whole project, not a second,
competing one.

Deliberately independent of the ``handbook.settings.settings``
singleton: that object is computed once, at import time, which makes it
awkward to (a) point at an isolated file in tests or (b) see a value
``cp-handbook init`` just wrote within the same process. ``SyncConfig``
re-reads the file fresh every time instead, so it's always accurate and
trivially testable.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "settings.toml"


@dataclass(slots=True)
class SyncConfig:
    """The subset of ``config/settings.toml`` the sync package cares about."""

    handle: str | None
    vault_path: Path | None
    config_path: Path

    @property
    def is_initialized(self) -> bool:
        """Has ``cp-handbook init`` been run (successfully) at least once?"""
        return bool(self.handle) and self.vault_path is not None

    @classmethod
    def load(cls, config_path: Path | None = None) -> SyncConfig:
        """Read the current configuration from ``config_path``.

        Defaults to the project's real ``config/settings.toml`` --
        pass an explicit path (e.g. a ``tmp_path`` file) to isolate a
        test from the real file entirely.
        """
        path = config_path or _DEFAULT_CONFIG_PATH
        data = _read_toml(path)
        vault_raw = data.get("vault", {}).get("path") or ""
        handle = data.get("codeforces", {}).get("handle") or None
        return cls(
            handle=handle,
            vault_path=Path(vault_raw).expanduser() if vault_raw else None,
            config_path=path,
        )

    def save(self) -> None:
        """Write this configuration back to :attr:`config_path`.

        Existing sections/keys this class doesn't know about (``[git]``,
        ``[templates]``, ``[notes]``) are preserved untouched; only
        ``[vault].path`` and ``[codeforces].handle`` are ever changed.
        """
        data = _read_toml(self.config_path)
        data.setdefault("vault", {})["path"] = (
            str(self.vault_path) if self.vault_path else ""
        )
        data.setdefault("git", {}).setdefault("auto_commit", True)
        data.setdefault("templates", {}).setdefault("path", "templates")
        data.setdefault("notes", {}).setdefault("default_author", "")
        data.setdefault("notes", {}).setdefault("auto_backlinks", True)
        data.setdefault("codeforces", {})["handle"] = self.handle or ""

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "wb") as f:
            tomli_w.dump(data, f)


def _read_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)
