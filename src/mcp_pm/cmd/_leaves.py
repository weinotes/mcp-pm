# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""leaves command — list servers not depended on by any other server (brew leaves equivalent)."""

from __future__ import annotations

from mcp_pm.cmd._helpers import _print_error, cli, console, escape
from mcp_pm.formula import FormulaManager


@cli.command()
def leaves() -> None:
    """List servers that are not depended on by any other server."""
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

        # Leaves = installed servers not referenced as a dependency
        leaf_names = sorted(all_names - referenced)

        if not leaf_names:
            console.print("[dim]All installed servers are depended on by others.[/dim]")
            return

        console.print("[bold]Leaf servers (not depended on by any other server):[/bold]")
        for leaf_name in leaf_names:
            console.print(f"  - [green]{escape(leaf_name)}[/green]")
        console.print(f"\n[dim]{len(leaf_names)} leaf server(s)[/dim]")

    except Exception as exc:
        _print_error(f"Failed to list leaves: {exc}")
        raise SystemExit(1) from exc
