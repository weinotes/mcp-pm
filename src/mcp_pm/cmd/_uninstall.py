# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""uninstall command — uninstall an MCP server by name."""

from __future__ import annotations

import click

from mcp_pm.cmd._helpers import (
    _async_run,
    _get_installer,
    _print_error,
    _print_success,
    cli,
    console,
    escape,
)


@cli.command()
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def uninstall(name: str, yes: bool) -> None:
    """Uninstall an MCP server by name."""
    try:
        if not yes:
            console.print(f"Uninstall server: [bold]{escape(name)}[/bold]")
            click.confirm("Are you sure?", default=False, abort=True)

        installer = _get_installer()
        success = _async_run(installer.uninstall(name))

        if success:
            _print_success(f"Uninstalled server '{name}'")
        else:
            _print_error(f"Server '{name}' is not installed.")

    except click.Abort:
        console.print("[yellow]Uninstall cancelled.[/yellow]")
        raise SystemExit(0) from None
    except Exception as exc:
        _print_error(f"Uninstall failed: {exc}")
        raise SystemExit(1) from exc
