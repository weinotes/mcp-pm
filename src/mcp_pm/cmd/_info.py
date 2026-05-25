# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""info command — show detailed info about an installed or registry MCP server."""

from __future__ import annotations

import click
from rich.box import MINIMAL
from rich.panel import Panel
from rich.table import Table

from mcp_pm.cmd._helpers import (
    _async_run,
    _create_progress,
    _get_installer,
    _get_registry,
    _print_error,
    cli,
    console,
    escape,
)


@cli.command()
@click.argument("name")
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def info(name: str, json_out: bool) -> None:
    """Show detailed info about an installed or registry MCP server."""
    try:
        # First check if installed
        installer = _get_installer()
        manifest = installer.get_manifest(name)

        if manifest:
            if json_out:
                console.print_json(data=manifest)
                return

            table = Table(box=MINIMAL, show_header=False, title=f"Server: {name}")
            table.add_column("Key", style="bold cyan", width=18)
            table.add_column("Value")

            for k, v in manifest.items():
                if k == "path":
                    continue
                table.add_row(str(k), escape(str(v)))

            console.print(Panel(table, border_style="cyan"))
            return

        # Check registry
        reg = _get_registry()
        with _create_progress(f"Looking up '{name}'...") as progress:
            task = progress.add_task("Querying...", total=None)
            remote = _async_run(reg.get(name))
            progress.update(task, completed=True)

        if remote is None:
            _print_error(f"Server '{name}' not found locally or in registries.")
            raise SystemExit(1)

        if json_out:
            console.print_json(data=remote.__dict__)
            return

        # Display remote info
        table = Table(box=MINIMAL, show_header=False, title=f"Registry: {name}")
        table.add_column("Key", style="bold cyan", width=18)
        table.add_column("Value")
        table.add_row("Name", escape(remote.name))
        table.add_row("Description", escape(remote.description))
        table.add_row("Source Type", remote.source_type)
        table.add_row("Source URL", escape(remote.source_url))
        table.add_row("Author", escape(remote.author or "-"))
        table.add_row("Homepage", escape(remote.homepage or "-"))
        table.add_row("License", escape(remote.license or "-"))
        table.add_row("Stars", str(remote.stars))
        table.add_row("Tools Count", str(remote.tools_count))
        if remote.tags:
            table.add_row("Tags", ", ".join(remote.tags))

        console.print(Panel(table, border_style="cyan"))

    except Exception as exc:
        _print_error(f"Info lookup failed: {exc}")
        raise SystemExit(1) from exc
