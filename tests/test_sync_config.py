"""Tests for handbook.sync.config.SyncConfig."""

from __future__ import annotations

from pathlib import Path

from handbook.sync.config import SyncConfig


def test_load_missing_file_returns_uninitialized_config(tmp_path: Path):
    config = SyncConfig.load(tmp_path / "settings.toml")

    assert config.handle is None
    assert config.vault_path is None
    assert config.is_initialized is False


def test_save_then_load_round_trips_handle_and_vault(tmp_path: Path):
    config_path = tmp_path / "settings.toml"
    config = SyncConfig.load(config_path)
    config.handle = "tourist"
    config.vault_path = tmp_path / "vault"
    config.save()

    reloaded = SyncConfig.load(config_path)

    assert reloaded.handle == "tourist"
    assert reloaded.vault_path == tmp_path / "vault"
    assert reloaded.is_initialized is True


def test_save_creates_parent_directories(tmp_path: Path):
    config_path = tmp_path / "nested" / "dir" / "settings.toml"
    config = SyncConfig.load(config_path)
    config.handle = "tourist"
    config.vault_path = tmp_path / "vault"

    config.save()

    assert config_path.exists()


def test_save_preserves_existing_git_templates_notes_sections(tmp_path: Path):
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        '[vault]\npath = ""\n\n'
        "[git]\nauto_commit = false\n\n"
        '[templates]\npath = "custom_templates"\n\n'
        '[notes]\ndefault_author = "Someone"\nauto_backlinks = false\n'
    )

    config = SyncConfig.load(config_path)
    config.handle = "tourist"
    config.vault_path = tmp_path / "vault"
    config.save()

    raw = config_path.read_text()
    assert "auto_commit = false" in raw
    assert 'path = "custom_templates"' in raw
    assert 'default_author = "Someone"' in raw
    assert "auto_backlinks = false" in raw


def test_save_only_touches_vault_path_and_codeforces_handle(tmp_path: Path):
    config_path = tmp_path / "settings.toml"
    config = SyncConfig.load(config_path)
    config.handle = "first-handle"
    config.vault_path = tmp_path / "vault-one"
    config.save()

    config2 = SyncConfig.load(config_path)
    config2.handle = "second-handle"
    config2.vault_path = tmp_path / "vault-two"
    config2.save()

    reloaded = SyncConfig.load(config_path)
    assert reloaded.handle == "second-handle"
    assert reloaded.vault_path == tmp_path / "vault-two"


def test_is_initialized_requires_both_handle_and_vault(tmp_path: Path):
    config_path = tmp_path / "settings.toml"

    only_handle = SyncConfig.load(config_path)
    only_handle.handle = "tourist"
    assert only_handle.is_initialized is False

    only_vault = SyncConfig.load(config_path)
    only_vault.vault_path = tmp_path / "vault"
    assert only_vault.is_initialized is False


def test_blank_handle_string_in_toml_is_treated_as_unset(tmp_path: Path):
    config_path = tmp_path / "settings.toml"
    config_path.write_text('[vault]\npath = ""\n\n[codeforces]\nhandle = ""\n')

    config = SyncConfig.load(config_path)

    assert config.handle is None
