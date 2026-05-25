# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""deps command — show dependencies of a formula (brew deps equivalent)."""

from __future__ import annotations

import click
from rich.tree import Tree

from mcp_pm.cmd._helpers import _print_error, cli, console, escape
from mcp_pm.formula import FormulaManager


@cli.command()
@click.argument("name")
@click.option("--tree", "tree_view", is_flag=True, help="Show dependency tree")
def deps(name: str, tree_view: bool) -> None:
    """Show dependencies for an MCP server formula."""
    try:
        fm = FormulaManager()
        formula = fm.load(name)
        if formula is None:
            _print_error(f"Server '{name}' is not installed.")
            raise SystemExit(1)

        dependencies = formula.dependencies
        if not dependencies:
            console.print(f"[dim]Server '{name}' has no dependencies.[/dim]")
            return

        if tree_view:
            tree = Tree(f"[bold]{escape(name)}[/bold]")
            for dep_name in dependencies:
                dep_node = tree.add(f"[cyan]{escape(dep_name)}[/cyan]")
                # Recursively show sub-dependencies
                sub_formula = fm.load(dep_name)
                if sub_formula and sub_formula.dependencies:
                    for sub_dep in sub_formula.dependencies:
                        dep_node.add(f"[dim]{escape(sub_dep)}[/dim]")
            console.print(tree)
        else:
            console.print(f"[bold]{escape(name)}[/bold] dependencies:")
            for dep_name in dependencies:
                console.print(f"  - [cyan]{escape(dep_name)}[/cyan]")
            console.print(f"\n[dim]{len(dependencies)} dependency(ies)[/dim]")

    except Exception as exc:
        _print_error(f"Failed to show dependencies: {exc}")
        raise SystemExit(1) from exc
