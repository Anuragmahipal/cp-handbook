"""Loads handbook configuration from config/settings.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path


class Settings:
    def __init__(self):
        config_path = Path(__file__).resolve().parents[2] / "config" / "settings.toml"

        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        self.vault = config["vault"]
        self.git = config["git"]
        self.templates = config["templates"]
        self.notes = config["notes"]

    @property
    def vault_path(self) -> Path:
        """Root directory for the handbook vault.

        Falls back to ``./vault`` when ``config/settings.toml`` has no
        path configured, so ``Handbook()`` works with zero setup.
        """
        raw = self.vault.get("path", "")
        if not raw:
            return Path.cwd() / "vault"
        return Path(raw).expanduser()


settings = Settings()
