# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""home command — open a server's homepage in the browser (brew home equivalent)."""

from __future__ import annotations

import webbrowser

import click

from mcp_pm.cmd._helpers import _print_error, cli, console, escape
from mcp_pm.formula import FormulaManager


@cli.command()
@click.argument("name")
def home(name: str) -> None:
    """Open a server's homepage in the browser."""
    try:
        fm = FormulaManager()
        formula = fm.load(name)
        if formula is None:
            _print_error(f"Server '{name}' is not installed.")
            raise SystemExit(1)

        url = formula.homepage or formula.source_url
        if not url:
            _print_error(f"No homepage or source URL found for '{name}'.")
            raise SystemExit(1)

        console.print(f"[dim]Opening {escape(url)} ...[/dim]")
        webbrowser.open(url)

    except Exception as exc:
        _print_error(f"Failed to open homepage: {exc}")
        raise SystemExit(1) from exc
