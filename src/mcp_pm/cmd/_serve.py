# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""serve command — start an HTTP proxy server that exposes all MCP tools via API."""

from __future__ import annotations

import contextlib

import click

from mcp_pm.client import MCPSession
from mcp_pm.cmd._helpers import (
    _async_run,
    _build_launch_command,
    _create_progress,
    _get_installer,
    _print_error,
    cli,
    console,
)

# We maintain a global session for the serve command so it can be
# shared by the proxy server during its lifecycle.
_session_for_serve: MCPSession | None = None


@cli.command()
@click.option("--port", "-p", default=8000, help="Proxy server port", type=int)
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--openai", is_flag=True, help="Enable OpenAI-compatible API")
@click.option("--log-level", default="info", help="Log level")
def serve(port: int, host: str, openai: bool, log_level: str) -> None:
    """Start an HTTP proxy server that exposes all MCP tools via API."""
    global _session_for_serve

    try:
        installer = _get_installer()
        servers = installer.list_installed()

        if not servers:
            _print_error("No servers installed. Run 'mcp pm install <source>' first.")
            raise SystemExit(1)

        session = MCPSession()

        console.print(f"Connecting to {len(servers)} installed server(s)...")

        with _create_progress("Connecting to MCP servers...") as progress:
            for srv in servers:
                name = srv.get("name", "?")
                task = progress.add_task(f"Connecting {name}...", total=None)

                try:
                    command = _build_launch_command(srv)
                    if command:
                        _async_run(session.start_server(name, command))
                        progress.update(task, completed=True, description=f"[green]\u2713 {name}[/green]")
                    else:
                        _print_error(f"  Cannot launch server '{name}': unknown command")
                        progress.update(task, completed=True, description=f"[red]\u2717 {name}[/red]")
                except Exception as exc:
                    _print_error(f"  Failed to start '{name}': {exc}")
                    progress.update(task, completed=True, description=f"[red]\u2717 {name}[/red]")

        if len(session.servers) == 0:
            _print_error("No servers could be started.")
            raise SystemExit(1)

        _session_for_serve = session
        console.print(
            f"[green]\u2713 Started {len(session.servers)} server(s) with "
            f"{len(session.get_all_tools())} tool(s)[/green]"
        )

        if not openai:
            console.print("[yellow]Note: --openai not set. Using default proxy mode.[/yellow]")

        from mcp_pm.server import start as start_proxy_server

        start_proxy_server(session, host=host, port=port, log_level=log_level)

    except SystemExit:
        raise
    except Exception as exc:
        _print_error(f"Failed to start proxy server: {exc}")
        raise SystemExit(1) from exc
    finally:
        if _session_for_serve is not None:
            with contextlib.suppress(Exception):
                _async_run(_session_for_serve.stop_all())
            _session_for_serve = None
