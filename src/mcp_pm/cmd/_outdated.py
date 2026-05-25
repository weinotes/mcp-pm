# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""outdated command — show outdated MCP servers with available updates."""

from __future__ import annotations

import click
from rich.box import ROUNDED
from rich.table import Table

from mcp_pm.cmd._helpers import (
    _async_run,
    _create_progress,
    _print_error,
    cli,
    console,
    escape,
)
from mcp_pm.formula import FormulaManager


@cli.command()
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def outdated(json_out: bool) -> None:
    """Show outdated MCP servers with available updates."""
    try:
        fm = FormulaManager()
        formulae = fm.list_formulae()

        if not formulae:
            console.print("[yellow]No servers installed.[/yellow]")
            return

        outdated_list: list[dict[str, str]] = []
        with _create_progress("Checking for updates...") as progress:
            task = progress.add_task("Querying versions...", total=len(formulae))
            for f in formulae:
                progress.update(task, description=f"Checking {f.name}...")
                latest = _async_run(fm.check_latest(f))
                status = fm.compare_versions(f.version, latest)
                if status in ("outdated", None):
                    outdated_list.append({
                        "name": f.name,
                        "current": f.version,
                        "latest": latest or "unknown",
                        "status": status or "unknown",
                    })
                progress.advance(task)
            progress.update(task, completed=True)

        if json_out:
            console.print_json(data=outdated_list)
            return

        if not outdated_list:
            console.print("[green]All servers are up to date![/green]")
            return

        table = Table(
            title="Outdated MCP Servers",
            box=ROUNDED,
            header_style="bold yellow",
        )
        table.add_column("Name", style="bold")
        table.add_column("Current", style="cyan")
        table.add_column("Latest", style="green")
        table.add_column("Status", style="yellow")

        for item in outdated_list:
            status_icon = "[red]OUTDATED[/red]" if item["status"] == "outdated" else "[dim]unknown[/dim]"
            table.add_row(
                escape(item["name"]),
                item["current"],
                item["latest"],
                status_icon,
            )

        console.print(table)
        console.print(f"\n[dim]{len(outdated_list)} server(s) outdated[/dim]")

    except Exception as exc:
        _print_error(f"Outdated check failed: {exc}")
        raise SystemExit(1) from exc
