# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""sandbox command — manage sandbox isolation for MCP servers."""

from __future__ import annotations

import click

from mcp_pm.cmd._helpers import _get_config, _print_error, _print_success, cli, console
from mcp_pm.exceptions import SandboxError
from mcp_pm.sandbox import SandboxLevel


@cli.command()
@click.argument("action", type=click.Choice(["on", "off", "status"]))
def sandbox(action: str) -> None:
    """Manage sandbox isolation for MCP servers."""
    try:
        cfg = _get_config()

        if action == "on":
            level = cfg.get("sandbox.level", "subprocess")
            try:
                sl = SandboxLevel(level)
            except ValueError:
                sl = SandboxLevel.SUBPROCESS
            cfg.set("sandbox.enabled", True)
            cfg.set("sandbox.level", sl.value)
            cfg.save()
            _print_success(f"Sandbox enabled (level: {sl.value})")

        elif action == "off":
            cfg.set("sandbox.enabled", False)
            cfg.save()
            _print_success("Sandbox disabled")

        elif action == "status":
            enabled = cfg.get("sandbox.enabled", False)
            level = cfg.get("sandbox.level", "off")
            if enabled:
                console.print(f"[green]Sandbox is ON[/green] (level: {level})")
            else:
                console.print("[yellow]Sandbox is OFF[/yellow]")

    except SandboxError as exc:
        _print_error(str(exc))
        raise SystemExit(1) from exc
    except Exception as exc:
        _print_error(f"Sandbox operation failed: {exc}")
        raise SystemExit(1) from exc
