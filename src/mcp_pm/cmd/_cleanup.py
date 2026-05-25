# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""cleanup command — remove stale cache and orphaned server directories."""

from __future__ import annotations

from pathlib import Path

import click
from rich.box import ROUNDED
from rich.table import Table

from mcp_pm.cmd._helpers import _print_error, cli, console, logger


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def cleanup(yes: bool) -> None:
    """Remove stale cache and orphaned server directories."""
    try:
        servers_dir = Path.home() / ".mcp-pm" / "servers"
        cache_dirs: list[Path] = []
        orphaned_dirs: list[Path] = []

        # Find orphaned dirs (no formula.yaml and no manifest.yaml)
        if servers_dir.exists():
            for entry in sorted(servers_dir.iterdir()):
                if not entry.is_dir():
                    continue
                formula_file = entry / "formula.yaml"
                manifest_file = entry / "manifest.yaml"
                if not formula_file.exists() and not manifest_file.exists():
                    orphaned_dirs.append(entry)

        if not orphaned_dirs and not cache_dirs:
            console.print("[green]Nothing to clean up![/green]")
            return

        # Report
        total_size = 0
        for d in orphaned_dirs:
            for f in d.rglob("*"):
                if f.is_file():
                    total_size += f.stat().st_size

        table = Table(
            title="Cleanup Summary",
            box=ROUNDED,
            header_style="bold cyan",
        )
        table.add_column("Type", style="yellow")
        table.add_column("Count", justify="right")
        table.add_column("Size")
        table.add_row("Orphaned directories", str(len(orphaned_dirs)),
                       f"{total_size / 1024:.1f} KB" if total_size > 0 else "-")

        console.print(table)

        if not yes:
            click.confirm("Remove these items?", default=False, abort=True)

        # Perform cleanup
        removed = 0
        for d in orphaned_dirs:
            import shutil

            shutil.rmtree(d, ignore_errors=True)
            removed += 1
            logger.info("Removed orphaned directory: %s", d)

        console.print(f"[green]\u2713 Cleaned up {removed} orphaned item(s).[/green]")

    except click.Abort:
        console.print("[yellow]Cleanup cancelled.[/yellow]")
        raise SystemExit(0) from None
    except Exception as exc:
        _print_error(f"Cleanup failed: {exc}")
        raise SystemExit(1) from exc
