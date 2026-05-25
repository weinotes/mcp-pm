# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""services command — manage running MCP server processes (brew services equivalent)."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

import click
from rich.table import Table

from mcp_pm.cmd._helpers import (
    _build_launch_command,
    _get_installer,
    _print_error,
    _print_success,
    cli,
    console,
    escape,
)

_SERVICES_DIR = Path.home() / ".mcp-pm" / "services"


def _get_pid_file(name: str) -> Path:
    _SERVICES_DIR.mkdir(parents=True, exist_ok=True)
    return _SERVICES_DIR / f"{name}.pid"


def _read_pid(name: str) -> int | None:
    pid_file = _get_pid_file(name)
    if pid_file.exists():
        try:
            return int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return None
    return None


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@cli.group()
def services() -> None:
    """Manage running MCP server processes (start/stop/restart/list)."""
    pass


@services.command("list")
def services_list() -> None:
    """List all running MCP servers."""
    try:
        _SERVICES_DIR.mkdir(parents=True, exist_ok=True)
        running: list[tuple[str, int]] = []

        for pid_file in sorted(_SERVICES_DIR.glob("*.pid")):
            name = pid_file.stem
            pid = _read_pid(name)
            if pid is not None and _is_running(pid):
                running.append((name, pid))

        if not running:
            console.print("[yellow]No MCP servers are currently running.[/yellow]")
            return

        table = Table(title="Running MCP Servers", header_style="bold cyan")
        table.add_column("Name", style="bold")
        table.add_column("PID", style="yellow")
        table.add_column("Status", style="green")

        for name, pid in running:
            table.add_row(escape(name), str(pid), "[green]Running[/green]")

        console.print(table)
        console.print(f"\n[dim]{len(running)} server(s) running[/dim]")

    except Exception as exc:
        _print_error(f"Failed to list services: {exc}")
        raise SystemExit(1) from exc


@services.command("start")
@click.argument("name")
def services_start(name: str) -> None:
    """Start an MCP server as a background process."""
    try:
        pid_file = _get_pid_file(name)
        existing_pid = _read_pid(name)
        if existing_pid is not None and _is_running(existing_pid):
            _print_error(f"Server '{name}' is already running (PID {existing_pid}).")
            raise SystemExit(1)

        installer = _get_installer()
        manifest = installer.get_manifest(name)
        if manifest is None:
            _print_error(f"Server '{name}' is not installed.")
            raise SystemExit(1)

        command = _build_launch_command(manifest)
        if not command:
            _print_error(f"Cannot determine launch command for '{name}'.")
            raise SystemExit(1)

        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        pid_file.write_text(str(process.pid))
        _print_success(f"Started server '{name}' (PID {process.pid})")

    except Exception as exc:
        _print_error(f"Failed to start server '{name}': {exc}")
        raise SystemExit(1) from exc


@services.command("stop")
@click.argument("name")
def services_stop(name: str) -> None:
    """Stop a running MCP server."""
    try:
        pid = _read_pid(name)
        if pid is None:
            _print_error(f"No PID found for server '{name}'. Is it running?")
            raise SystemExit(1)

        if not _is_running(pid):
            _print_error(f"Server '{name}' is not running (stale PID {pid}).")
            _get_pid_file(name).unlink(missing_ok=True)
            raise SystemExit(1)

        os.kill(pid, signal.SIGTERM)
        _get_pid_file(name).unlink(missing_ok=True)
        _print_success(f"Stopped server '{name}' (PID {pid})")

    except Exception as exc:
        _print_error(f"Failed to stop server '{name}': {exc}")
        raise SystemExit(1) from exc


@services.command("restart")
@click.argument("name")
def services_restart(name: str) -> None:
    """Restart a running MCP server."""
    try:
        pid_file = _get_pid_file(name)
        pid = _read_pid(name)
        if pid is not None and _is_running(pid):
            os.kill(pid, signal.SIGTERM)
            pid_file.unlink(missing_ok=True)
            console.print(f"[dim]Stopped PID {pid}[/dim]")

        installer = _get_installer()
        manifest = installer.get_manifest(name)
        if manifest is None:
            _print_error(f"Server '{name}' is not installed.")
            raise SystemExit(1)

        command = _build_launch_command(manifest)
        if not command:
            _print_error(f"Cannot determine launch command for '{name}'.")
            raise SystemExit(1)

        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        pid_file.write_text(str(process.pid))
        _print_success(f"Restarted server '{name}' (PID {process.pid})")

    except Exception as exc:
        _print_error(f"Failed to restart server '{name}': {exc}")
        raise SystemExit(1) from exc
