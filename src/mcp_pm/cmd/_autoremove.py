# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""autoremove command — uninstall all orphaned servers (brew autoremove equivalent)."""

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
    logger,
)
from mcp_pm.formula import FormulaManager


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def autoremove(yes: bool) -> None:
    """Uninstall all servers that are not depended on by any other server."""
    try:
        fm = FormulaManager()
        formulae = fm.list_formulae()

        if not formulae:
            console.print("[yellow]No servers installed.[/yellow]")
            return

        # Collect all names and all dependency references
        all_names = {f.name for f in formulae}
        referenced: set[str] = set()
        for f in formulae:
            for dep in f.dependencies:
                referenced.add(dep)

        orphaned = sorted(all_names - referenced)

        if not orphaned:
            console.print("[green]No orphaned servers to remove.[/green]")
            return

        console.print("[bold]Orphaned servers to remove:[/bold]")
        for orphan in orphaned:
            console.print(f"  - [yellow]{escape(orphan)}[/yellow]")

        if not yes:
            click.confirm(f"Remove {len(orphaned)} orphaned server(s)?", default=False, abort=True)

        installer = _get_installer()
        removed = 0
        for orphan in orphaned:
            ok = _async_run(installer.uninstall(orphan))
            if ok:
                removed += 1
                logger.info("Autoremoved orphaned server: %s", orphan)

        if removed > 0:
            _print_success(f"Removed {removed} orphaned server(s).")
        else:
            console.print("[yellow]No servers were removed.[/yellow]")

    except click.Abort:
        console.print("[yellow]Autoremove cancelled.[/yellow]")
        raise SystemExit(0) from None
    except Exception as exc:
        _print_error(f"Autoremove failed: {exc}")
        raise SystemExit(1) from exc
