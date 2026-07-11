"""Tests for handbook.sync.cli: init / sync / status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from handbook.sync.cli import main
from handbook.sync.codeforces import CodeforcesClient
from handbook.sync.config import SyncConfig


def _client(payloads: list[dict]) -> CodeforcesClient:
    response = {"status": "OK", "result": payloads}

    def _transport(url: str) -> bytes:
        return json.dumps(response).encode()

    return CodeforcesClient(transport=_transport)


def _failing_client(comment: str = "handle: User not found") -> CodeforcesClient:
    def _transport(url: str) -> bytes:
        return json.dumps({"status": "FAILED", "comment": comment}).encode()

    return CodeforcesClient(transport=_transport)


# -- init -----------------------------------------------------------------


def test_init_with_flags_writes_config(tmp_path: Path):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "vault"

    exit_code = main(
        ["init", "--handle", "tourist", "--vault", str(vault_path)],
        config_path=config_path,
    )

    assert exit_code == 0
    config = SyncConfig.load(config_path)
    assert config.handle == "tourist"
    assert config.vault_path == vault_path.resolve()


def test_init_creates_the_vault_directory(tmp_path: Path):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "does" / "not" / "exist" / "yet"

    main(
        ["init", "--handle", "tourist", "--vault", str(vault_path)],
        config_path=config_path,
    )

    assert vault_path.exists()


def test_init_without_handle_and_no_tty_fails_cleanly(tmp_path: Path):
    config_path = tmp_path / "settings.toml"

    exit_code = main(
        ["init", "--vault", str(tmp_path / "vault")], config_path=config_path
    )

    assert exit_code == 1
    config = SyncConfig.load(config_path)
    assert config.handle is None


def test_init_is_idempotent_and_updates_existing_config(tmp_path: Path):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "vault"
    main(
        ["init", "--handle", "old-handle", "--vault", str(vault_path)],
        config_path=config_path,
    )

    main(
        ["init", "--handle", "new-handle", "--vault", str(vault_path)],
        config_path=config_path,
    )

    config = SyncConfig.load(config_path)
    assert config.handle == "new-handle"


# -- sync -------------------------------------------------------------------


def test_sync_before_init_fails_with_clear_message(tmp_path: Path):
    config_path = tmp_path / "settings.toml"

    exit_code = main(["sync"], config_path=config_path)

    assert exit_code == 1


def test_sync_after_init_imports_and_reports(tmp_path: Path, cf_submission_payload):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "vault"
    main(
        ["init", "--handle", "tourist", "--vault", str(vault_path)],
        config_path=config_path,
    )

    client = _client([cf_submission_payload(id=1)])
    exit_code = main(["sync"], config_path=config_path, client=client)

    assert exit_code == 0
    assert (vault_path / "Problems").exists()
    assert (vault_path / "Revision Notes").exists()
    assert (vault_path / ".handbook" / "graph.json").exists()


def test_sync_is_idempotent_via_cli(tmp_path: Path, cf_submission_payload):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "vault"
    main(
        ["init", "--handle", "tourist", "--vault", str(vault_path)],
        config_path=config_path,
    )
    client = _client([cf_submission_payload(id=1)])

    first_exit = main(["sync"], config_path=config_path, client=client)
    second_exit = main(["sync"], config_path=config_path, client=client)

    assert first_exit == 0
    assert second_exit == 0
    problem_files = list((vault_path / "Problems").glob("*.md"))
    assert len(problem_files) == 1


def test_sync_handle_override_does_not_persist(tmp_path: Path, cf_submission_payload):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "vault"
    main(
        ["init", "--handle", "configured-handle", "--vault", str(vault_path)],
        config_path=config_path,
    )
    client = _client([cf_submission_payload(id=1)])

    main(
        ["sync", "--handle", "override-handle"], config_path=config_path, client=client
    )

    config = SyncConfig.load(config_path)
    assert config.handle == "configured-handle"


def test_sync_reports_api_error(tmp_path: Path):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "vault"
    main(
        ["init", "--handle", "tourist", "--vault", str(vault_path)],
        config_path=config_path,
    )

    exit_code = main(["sync"], config_path=config_path, client=_failing_client())

    assert exit_code == 1


# -- status -----------------------------------------------------------------


def test_status_before_init(tmp_path: Path):
    config_path = tmp_path / "settings.toml"

    exit_code = main(["status"], config_path=config_path)

    assert exit_code == 0  # status is informational, never an error


def test_status_after_init_before_sync(tmp_path: Path):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "vault"
    main(
        ["init", "--handle", "tourist", "--vault", str(vault_path)],
        config_path=config_path,
    )

    exit_code = main(["status"], config_path=config_path)

    assert exit_code == 0


def test_status_after_sync_reflects_known_problems(
    tmp_path: Path, cf_submission_payload
):
    config_path = tmp_path / "settings.toml"
    vault_path = tmp_path / "vault"
    main(
        ["init", "--handle", "tourist", "--vault", str(vault_path)],
        config_path=config_path,
    )
    client = _client([cf_submission_payload(id=1)])
    main(["sync"], config_path=config_path, client=client)

    exit_code = main(["status"], config_path=config_path)

    assert exit_code == 0


# -- parser -----------------------------------------------------------------


def test_missing_subcommand_exits_nonzero_via_argparse():
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code != 0
