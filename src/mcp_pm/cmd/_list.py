# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""list command — list all installed MCP servers and their tools."""

from __future__ import annotations

import click
from rich.box import ROUNDED
from rich.table import Table
from rich.tree import Tree

from mcp_pm.cmd._helpers import (
    _get_installer,
    _list_tools_for_server,
    _print_error,
    cli,
    console,
    escape,
)


@cli.command("list")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json", "tree"]),
    default="table",
    help="Output format",
)
@click.option("--tools", is_flag=True, help="List tools for each server")
def list_servers(fmt: str, tools: bool) -> None:
    """List all installed MCP servers and their tools."""
    try:
        installer = _get_installer()
        servers = installer.list_installed()

        if not servers:
            console.print("[yellow]No servers installed.[/yellow]")
            return

        if fmt == "json":
            output = []
            for srv in servers:
                entry = dict(srv)
                if tools:
                    entry["tools"] = _list_tools_for_server(srv["name"])
                output.append(entry)
            console.print_json(data=output)
            return

        if fmt == "tree":
            tree = Tree("\U0001f4e6 [bold]MCP Servers[/bold]")
            for srv in servers:
                label = f"[bold]{escape(srv.get('name', '?'))}[/bold]"
                if srv.get("version"):
                    label += f" [dim]v{srv['version']}[/dim]"
                if srv.get("source_type"):
                    label += f" [cyan]({srv['source_type']})[/cyan]"
                branch = tree.add(label)
                if srv.get("description"):
                    branch.add(f"[dim]{escape(srv['description'][:80])}[/dim]")
                if tools:
                    tool_list = _list_tools_for_server(srv["name"])
                    if tool_list:
                        tools_node = branch.add("[yellow]Tools:[/yellow]")
                        for t in tool_list:
                            tools_node.add(f"[green]{escape(t['name'])}[/green]")
            console.print(tree)
            return

        # Table format
        table = Table(
            title="Installed MCP Servers",
            box=ROUNDED,
            header_style="bold cyan",
        )
        table.add_column("Name", style="bold")
        table.add_column("Type", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Source", style="dim")
        table.add_column("Installed At")

        if tools:
            table.add_column("Tools", style="yellow")

        for srv in servers:
            tools_str = ""
            if tools:
                tool_list = _list_tools_for_server(srv["name"])
                tools_str = ", ".join(t["name"] for t in tool_list[:5])
                if len(tool_list) > 5:
                    tools_str += f" ... (+{len(tool_list) - 5})"

            table.add_row(
                escape(srv.get("name", "?")),
                srv.get("source_type", "?"),
                srv.get("version", "?"),
                escape(srv.get("source_url", "")[:60]),
                srv.get("installed_at", "")[:19],
                tools_str if tools else "",
            )

        console.print(table)

        # Summary line
        total_tools = 0
        if tools:
            for srv in servers:
                total_tools += len(_list_tools_for_server(srv["name"]))
            console.print(
                f"\n[dim]{len(servers)} server(s), {total_tools} tool(s) total[/dim]"
            )
        else:
            console.print(f"\n[dim]{len(servers)} server(s) installed[/dim]")

    except Exception as exc:
        _print_error(f"Failed to list servers: {exc}")
        raise SystemExit(1) from exc
