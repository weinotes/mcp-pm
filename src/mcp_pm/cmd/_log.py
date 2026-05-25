# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""log command — show server install/update logs (brew log equivalent)."""

from __future__ import annotations

from pathlib import Path

import click

from mcp_pm.cmd._helpers import _print_error, cli, console, escape

_LOG_DIR = Path.home() / ".mcp-pm" / "logs"


@cli.command()
@click.argument("name")
@click.option("--lines", "-n", default=50, help="Number of lines to show", type=int)
@click.option("--follow", "-f", is_flag=True, help="Follow log output (tail)")
def log(name: str, lines: int, follow: bool) -> None:
    """Show install/update logs for a server."""
    try:
        server_log = _LOG_DIR / f"{name}.log"
        general_log = _LOG_DIR / "mcp-pm.log"

        log_file = server_log if server_log.exists() else general_log
        if not log_file.exists() and not server_log.exists():
            log_file = None

        if log_file is None:
            _print_error(f"No logs found for server '{name}'.")
            raise SystemExit(1)

        if follow:
            import subprocess
            import sys as _sys
            try:
                proc = subprocess.Popen(
                    ["tail", "-n", str(lines), "-f", str(log_file)],
                    stdout=_sys.stdout, stderr=_sys.stderr,
                )
                proc.wait()
            except FileNotFoundError:
                content = log_file.read_text(encoding="utf-8")
                console.print(content)
        else:
            content = log_file.read_text(encoding="utf-8")
            log_lines = content.strip().splitlines()
            tail_lines = log_lines[-lines:] if len(log_lines) > lines else log_lines
            console.print(f"[bold]Log: {escape(str(log_file))}[/bold]")
            shown = min(lines, len(log_lines))
            console.print(f"[dim]Showing last {shown} of {len(log_lines)} lines[/dim]")
            for line in tail_lines:
                console.print(line)

    except Exception as exc:
        _print_error(f"Failed to read log: {exc}")
        raise SystemExit(1) from exc
