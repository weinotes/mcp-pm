# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""tap command group — manage third-party tap repositories."""

from __future__ import annotations

import click
from rich.box import ROUNDED
from rich.table import Table

from mcp_pm.cmd._helpers import _async_run, _print_error, _print_success, cli, console


@cli.group()
def tap() -> None:
    """Manage third-party tap repositories."""
    pass


@tap.command("add")
@click.argument("name")
@click.option("--url", help="Git URL (default: https://github.com/{name}.git)")
def tap_add(name: str, url: str | None) -> None:
    """Add a third-party tap from GitHub.

    NAME should be in ``owner/repo`` format, e.g. ``weinotes/mcp-tap``.
    """
    from mcp_pm.tap import TapManager

    try:
        tm = TapManager()
        result = _async_run(tm.add(name, repo_url=url))
        _print_success(f"Tap '{result.name}' added from {result.repo_url}")
        console.print(f"  Location: {result.path}")
    except ValueError as exc:
        _print_error(str(exc))
        raise SystemExit(1) from exc
    except Exception as exc:
        _print_error(f"Failed to add tap: {exc}")
        raise SystemExit(1) from exc


@tap.command("list")
def tap_list() -> None:
    """List installed taps."""
    from mcp_pm.tap import TapManager

    try:
        tm = TapManager()
        taps = tm.list_taps()
        if not taps:
            console.print("[yellow]No taps installed.[/yellow]")
            return

        table = Table(
            title="Installed Taps",
            box=ROUNDED,
            header_style="bold cyan",
        )
        table.add_column("Name", style="bold")
        table.add_column("Repository", style="dim")
        table.add_column("Path", style="green")
        for t in taps:
            table.add_row(t.name, t.repo_url, str(t.path))
        console.print(table)
    except Exception as exc:
        _print_error(f"Failed to list taps: {exc}")
        raise SystemExit(1) from exc


@tap.command("remove")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def tap_remove(name: str, yes: bool) -> None:
    """Remove an installed tap."""
    from mcp_pm.tap import TapManager

    try:
        tm = TapManager()
        tap_obj = tm.get_tap(name)
        if tap_obj is None:
            _print_error(f"Tap '{name}' is not installed.")
            raise SystemExit(1)

        if not yes:
            click.confirm(f"Remove tap '{tap_obj.name}'?", default=False, abort=True)

        if tm.remove(name):
            _print_success(f"Tap '{name}' removed.")
        else:
            _print_error(f"Failed to remove tap '{name}'.")
            raise SystemExit(1)
    except click.Abort:
        console.print("[yellow]Cancelled.[/yellow]")
        raise SystemExit(0) from None
    except Exception as exc:
        _print_error(f"Failed to remove tap: {exc}")
        raise SystemExit(1) from exc
