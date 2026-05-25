# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""run command — run an MCP tool directly from the CLI."""

from __future__ import annotations

import json
from typing import Any

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
from mcp_pm.exceptions import McpPmError


@cli.command()
@click.argument("server")
@click.argument("tool")
@click.argument("args", nargs=-1)
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def run(server: str, tool: str, args: tuple[str, ...], json_out: bool) -> None:
    """Run an MCP tool directly from the CLI.

    Arguments should be passed as key=value pairs, e.g.:

        mcp run my-server my-tool text="hello world" count=5
    """
    try:
        installer = _get_installer()
        manifest = installer.get_manifest(server)

        if manifest is None:
            _print_error(f"Server '{server}' is not installed.")
            raise SystemExit(1)

        command = _build_launch_command(manifest)
        if not command:
            _print_error(f"Cannot determine launch command for '{server}'.")
            raise SystemExit(1)

        # Parse key=value arguments
        tool_args: dict[str, Any] = {}
        for arg in args:
            if "=" in arg:
                k, v = arg.split("=", 1)
                # Try parsing as int/float/bool
                parsed: Any = v
                if v.lower() in ("true", "false"):
                    parsed = v.lower() == "true"
                elif v.lower() == "null":
                    parsed = None
                else:
                    try:
                        parsed = int(v)
                    except ValueError:
                        try:
                            parsed = float(v)
                        except ValueError:
                            parsed = v
                tool_args[k] = parsed
            else:
                tool_args[arg] = True

        session = MCPSession()
        with _create_progress(f"Connecting to '{server}'...") as progress:
            task = progress.add_task("Connecting...", total=None)
            _async_run(session.start_server(server, command))
            progress.update(task, completed=True, description=f"[green]\u2713 {server}[/green]")

        console.print(f"[dim]Calling {server}/{tool}...[/dim]")
        result = _async_run(session.call_tool(server, tool, tool_args))

        _async_run(session.stop_server(server))

        if json_out:
            output_data = {
                "content": result.content,
                "is_error": result.is_error,
            }
            console.print_json(data=output_data)
        else:
            for item in result.content:
                if isinstance(item, dict):
                    text = item.get("text", json.dumps(item, ensure_ascii=False))
                    console.print(text)
                else:
                    console.print(str(item))

    except KeyError:
        _print_error(f"Server '{server}' not found in session.")
        raise SystemExit(1) from None
    except McpPmError as exc:
        _print_error(str(exc))
        raise SystemExit(1) from exc
    except Exception as exc:
        _print_error(f"Tool call failed: {exc}")
        raise SystemExit(1) from exc
