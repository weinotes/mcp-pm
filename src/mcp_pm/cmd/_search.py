# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""search command — search for MCP servers in the registry."""

from __future__ import annotations

import click
from rich.box import ROUNDED
from rich.table import Table

from mcp_pm.cmd._helpers import (
    _async_run,
    _create_progress,
    _get_registry,
    _print_error,
    cli,
    console,
    escape,
)
from mcp_pm.registry import ServerManifest


@cli.command()
@click.argument("query", required=False, default="")
@click.option("--limit", "-l", default=20, help="Max results", type=int)
@click.option("--registry", help="Backend registry to use")
@click.option("--popular", is_flag=True, help="List popular servers instead of searching")
def search(query: str, limit: int, registry: str | None, popular: bool) -> None:
    """Search for MCP servers in the registry."""
    try:
        reg = _get_registry()

        with _create_progress("Searching registries...") as progress:
            task = progress.add_task("Searching...", total=None)

            if popular:
                results = _async_run(reg.popular(limit))
            else:
                results = _async_run(reg.search(query, limit))

            progress.update(task, completed=True)

        if not results:
            msg = "No popular servers found." if popular else f"No results for '{query}'."
            console.print(f"[yellow]{escape(msg)}[/yellow]")
            return

        # Sort by relevance (name match > description/author > stars tiebreaker)
        def _relevance_key(m: ServerManifest) -> tuple:
            q_lower = query.lower() if query else ""
            if not q_lower:
                return (0, -m.stars)
            name_match = 2 if q_lower in m.name.lower() else 0
            desc_match = 1 if q_lower in m.description.lower() else 0
            author_match = 1 if m.author and q_lower in m.author.lower() else 0
            return (-(name_match + desc_match + author_match), -m.stars)

        results.sort(key=_relevance_key)

        table = Table(
            title=f"{'Popular' if popular else f'Search: {query}'} MCP Servers",
            box=ROUNDED,
            header_style="bold cyan",
        )
        table.add_column("Name", style="bold")
        table.add_column("Description", style="dim")
        table.add_column("Stars", style="yellow", justify="right")
        table.add_column("Type", style="cyan")
        table.add_column("Source")

        for m in results:
            desc = m.description[:60] + "..." if len(m.description) > 60 else m.description
            table.add_row(
                escape(m.name),
                escape(desc),
                str(m.stars) if m.stars else "-",
                m.source_type,
                escape(m.source_url[:50]) if m.source_url else "-",
            )

        console.print(table)
        console.print(f"[dim]{len(results)} result(s)[/dim]")

    except Exception as exc:
        _print_error(f"Search failed: {exc}")
        raise SystemExit(1) from exc
