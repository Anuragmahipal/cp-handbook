"""``cp-handbook`` command-line interface: init / sync / status.

Kept deliberately thin: every subcommand handler resolves a
:class:`~handbook.sync.config.SyncConfig`, then delegates to
:mod:`handbook.sync.pipeline` or :mod:`handbook.sync.state` for
anything that isn't purely about argument parsing or console output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from handbook.sync.codeforces import (
    CodeforcesAPIError,
    CodeforcesClient,
    CodeforcesTransportError,
)
from handbook.sync.config import SyncConfig
from handbook.sync.pipeline import SyncReport, run_sync
from handbook.sync.state import SyncState
from handbook.utils.filesystem import ensure_directory

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cp-handbook",
        description="Sync solved Codeforces problems into the CP Handbook vault.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="Configure a Codeforces handle and vault location."
    )
    init_parser.add_argument("--handle", help="Codeforces handle.")
    init_parser.add_argument("--vault", help="Vault directory.")

    sync_parser = subparsers.add_parser(
        "sync", help="Fetch new accepted submissions and update the vault."
    )
    sync_parser.add_argument(
        "--handle", help="Override the configured Codeforces handle for this run."
    )
    sync_parser.add_argument(
        "--count",
        type=int,
        default=10_000,
        help="Max submissions to fetch from Codeforces (default: 10000).",
    )

    subparsers.add_parser("status", help="Show configuration and sync state.")

    return parser


def main(
    argv: list[str] | None = None,
    *,
    config_path: Path | None = None,
    client: CodeforcesClient | None = None,
) -> int:
    """Entry point. Returns a process exit code.

    ``config_path`` and ``client`` are test seams -- production callers
    (the installed ``cp-handbook`` console script) never pass them, so
    they default to the real project config file and a real
    :class:`CodeforcesClient` respectively.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return cmd_init(args, config_path=config_path)
    if args.command == "sync":
        return cmd_sync(args, config_path=config_path, client=client)
    if args.command == "status":
        return cmd_status(args, config_path=config_path)

    parser.print_help()  # pragma: no cover - argparse `required=True` prevents this
    return 1


def cmd_init(args: argparse.Namespace, *, config_path: Path | None = None) -> int:
    config = SyncConfig.load(config_path)

    handle = args.handle or _prompt("Codeforces handle", default=config.handle)
    if not handle:
        console.print("[red]A Codeforces handle is required.[/red]")
        return 1

    default_vault = (
        str(config.vault_path) if config.vault_path else str(Path.cwd() / "vault")
    )
    vault_raw = args.vault or _prompt("Vault directory", default=default_vault)
    if not vault_raw:
        console.print("[red]A vault directory is required.[/red]")
        return 1
    vault_path = Path(vault_raw).expanduser().resolve()
    ensure_directory(vault_path)

    config.handle = handle
    config.vault_path = vault_path
    config.save()

    console.print(
        f"[green]\u2713[/green] Configured handle [bold]{handle}[/bold] "
        f"and vault at [bold]{vault_path}[/bold]."
    )
    console.print(f"  Config written to {config.config_path}")
    console.print(
        "\nRun [bold]cp-handbook sync[/bold] to fetch your accepted submissions."
    )
    return 0


def _prompt(label: str, *, default: str | None) -> str:
    """Prompt interactively, or fall back to ``default`` when there's no TTY
    (a non-interactive test/CI invocation) rather than blocking forever."""
    if not sys.stdin.isatty():
        return default or ""
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or (default or "")


def cmd_sync(
    args: argparse.Namespace,
    *,
    config_path: Path | None = None,
    client: CodeforcesClient | None = None,
) -> int:
    config = SyncConfig.load(config_path)
    if not config.is_initialized:
        console.print(
            "[red]Not configured yet.[/red] Run [bold]cp-handbook init[/bold] first."
        )
        return 1

    handle = args.handle or config.handle
    cf_client = client if client is not None else CodeforcesClient()
    assert config.vault_path is not None  # guaranteed by is_initialized above

    console.print(f"Syncing [bold]{handle}[/bold] -> {config.vault_path} ...")
    try:
        report = run_sync(
            handle, vault_root=config.vault_path, client=cf_client, count=args.count
        )
    except CodeforcesAPIError as exc:
        console.print(f"[red]Codeforces API error:[/red] {exc}")
        return 1
    except CodeforcesTransportError as exc:
        console.print(f"[red]Network error:[/red] {exc}")
        return 1

    _print_report(report)
    return 0


def _print_report(report: SyncReport) -> None:
    console.print(
        f"Fetched {report.fetched_submissions} submissions "
        f"({report.newly_accepted} new accepted)."
    )

    if report.imported:
        table = Table(title="New problems imported")
        table.add_column("Problem")
        table.add_column("Rating")
        table.add_column("Revision note")
        for synced in report.imported:
            table.add_row(
                synced.item.title,
                str(synced.item.rating) if synced.item.rating is not None else "\u2014",
                str(synced.note_paths.markdown_path),
            )
        console.print(table)
    else:
        console.print("No new problems to import.")

    if report.duplicate_report is not None and not report.duplicate_report.is_empty():
        console.print(
            "[yellow]\u26a0 Possible duplicates detected in the graph "
            "-- see `cp-handbook status`.[/yellow]"
        )

    if report.notebook_pages:
        console.print(
            f"Compiled [bold]{len(report.notebook_pages)}[/bold] notebook "
            f"page(s) into {report.notebook_pages[0].html_path.parent.parent}/"
        )

    if report.materialization is not None and report.materialization.created:
        console.print(
            f"Materialized [bold]{len(report.materialization.created)}[/bold] "
            "new knowledge item(s): "
            + ", ".join(
                f"{m.item.title} ({m.item.KIND})" for m in report.materialization.created
            )
        )
    if report.materialization is not None and report.materialization.warnings:
        for warning in report.materialization.warnings:
            console.print(f"[yellow]\u26a0 {warning}[/yellow]")

    if report.notebook_site is not None and report.notebook_site.pages:
        console.print(
            f"Notebook site: [bold]{len(report.notebook_site.pages)}[/bold] page(s), "
            f"dashboard at {report.notebook_site.dashboard_path}"
        )

    if report.evolution is not None and not report.evolution.is_empty:
        parts = []
        if report.evolution.learning_events:
            parts.append(f"{len(report.evolution.learning_events)} new learning event(s)")
        if report.evolution.knowledge_growth:
            parts.append(f"{len(report.evolution.knowledge_growth)} knowledge growth update(s)")
        if report.evolution.mastery_changes:
            parts.append(f"{len(report.evolution.mastery_changes)} mastery change(s)")
        console.print("Evolution: " + ", ".join(parts))

    console.print(
        f"\n[bold]{report.total_known_problems}[/bold] known problems  \u00b7  "
        f"graph: {report.graph_node_count} nodes / {report.graph_edge_count} edges"
    )


def cmd_status(args: argparse.Namespace, *, config_path: Path | None = None) -> int:
    config = SyncConfig.load(config_path)

    table = Table(title="cp-handbook status", show_header=False)
    table.add_row("Handle", config.handle or "[red]not set[/red]")
    table.add_row(
        "Vault", str(config.vault_path) if config.vault_path else "[red]not set[/red]"
    )

    if not config.is_initialized:
        console.print(table)
        console.print("\nRun [bold]cp-handbook init[/bold] to get started.")
        return 0

    assert config.vault_path is not None
    state = SyncState(config.vault_path)
    table.add_row("Known problems", str(state.problem_count()))
    table.add_row("Imported submissions", str(state.imported_count()))
    table.add_row(
        "Last synced",
        state.last_synced_at.strftime("%Y-%m-%d %H:%M:%S")
        if state.last_synced_at
        else "never",
    )
    console.print(table)

    if state.last_synced_at is None:
        console.print(
            "\nRun [bold]cp-handbook sync[/bold] to fetch your accepted submissions."
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
