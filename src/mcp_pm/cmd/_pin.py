# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""pin / unpin commands — mark servers as pinned to protect from updates."""

from __future__ import annotations

import click

from mcp_pm.cmd._helpers import _print_error, _print_success, cli, console, logger
from mcp_pm.formula import FormulaManager


@cli.command()
@click.argument("name")
def pin(name: str) -> None:
    """Pin a server to prevent it from being updated."""
    try:
        fm = FormulaManager()
        formula = fm.load(name)
        if formula is None:
            _print_error(f"Server '{name}' is not installed.")
            raise SystemExit(1)

        if formula.pinned:
            console.print(f"[yellow]Server '{name}' is already pinned.[/yellow]")
            return

        formula.pinned = True
        fm.save(formula)
        _print_success(f"Pinned server '{name}'. It will be skipped during updates.")
        logger.info("Pinned server: %s", name)

    except Exception as exc:
        _print_error(f"Failed to pin server: {exc}")
        raise SystemExit(1) from exc


@cli.command()
@click.argument("name")
def unpin(name: str) -> None:
    """Unpin a server to allow updates again."""
    try:
        fm = FormulaManager()
        formula = fm.load(name)
        if formula is None:
            _print_error(f"Server '{name}' is not installed.")
            raise SystemExit(1)

        if not formula.pinned:
            console.print(f"[yellow]Server '{name}' is not pinned.[/yellow]")
            return

        formula.pinned = False
        fm.save(formula)
        _print_success(f"Unpinned server '{name}'. It can now be updated.")
        logger.info("Unpinned server: %s", name)

    except Exception as exc:
        _print_error(f"Failed to unpin server: {exc}")
        raise SystemExit(1) from exc
