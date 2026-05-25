# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""Shared utilities for mcp-pm CLI commands."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import click
from rich.box import MINIMAL
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from mcp_pm.client import MCPSession
from mcp_pm.config import Config
from mcp_pm.installer import Installer
from mcp_pm.registry import RegistryManager

# ---------------------------------------------------------------------------
# Logging setup — writes to ~/.mcp-pm/logs/mcp-pm.log
# ---------------------------------------------------------------------------

_LOG_DIR = Path.home() / ".mcp-pm" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "mcp-pm.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(_LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("mcp-pm.cli")

# ---------------------------------------------------------------------------
# Rich console
# ---------------------------------------------------------------------------

console = Console()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _async_run(coro: Any) -> Any:
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.ensure_future(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _print_error(msg: str) -> None:
    console.print(f"[red]\u2717[/red] {escape(msg)}")


def _print_success(msg: str) -> None:
    console.print(f"[green]\u2713[/green] {escape(msg)}")


def _get_config() -> Config:
    cfg = Config()
    cfg.load()
    return cfg


def _get_installer() -> Installer:
    return Installer()


def _get_registry() -> RegistryManager:
    return RegistryManager()


def _create_progress(description: str = "Working...") -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def _detect_source_type(source: str) -> str | None:
    """Try to guess the source type from the URL / string."""
    if source.startswith("http") or source.startswith("git@"):
        return "git"
    if source.startswith("npm") or source.startswith("@") or "/npm/" in source:
        return "npm"
    if source.startswith("pip:") or source.startswith("uvx"):
        return "pip"
    if source.startswith("docker:") or source.startswith("docker.io"):
        return "docker"
    # If it looks like a package name without protocol, default to pip
    if "/" not in source and not source.startswith("http"):
        return "pip"
    return None


def _derive_name(source: str) -> str:
    """Derive a server name from the source string."""
    # Strip protocol
    name = source.rsplit("/", 1)[-1] if "/" in source else source
    # Strip common prefixes
    for prefix in ("pip:", "npm:", "docker:", "uvx ", "uvx:"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    # Strip .git suffix
    if name.endswith(".git"):
        name = name[:-4]
    return name.strip()


def _show_server_brief(meta: dict[str, Any]) -> None:
    """Show a brief server info panel after install."""
    table = Table(box=MINIMAL, show_header=False)
    table.add_column("Key", style="bold cyan", width=16)
    table.add_column("Value")
    for k, v in meta.items():
        if k == "path":
            continue
        table.add_row(str(k), escape(str(v)))
    console.print(Panel(table, title="Server Info", border_style="green"))


def _list_tools_for_server(server_name: str) -> list[dict[str, Any]]:
    """Try to connect to an installed server and list its tools."""
    installer = _get_installer()
    manifest = installer.get_manifest(server_name)
    if not manifest:
        return []

    # Attempt to start a session and list tools
    session = MCPSession()
    try:
        command = _build_launch_command(manifest)
        if command:
            _async_run(session.start_server(server_name, command))
            tools_info = []
            for _srv_name, tool in session.get_all_tools():
                tools_info.append({
                    "name": tool.name,
                    "description": tool.description[:80] if tool.description else "",
                })
            _async_run(session.stop_server(server_name))
            return tools_info
    except Exception as exc:
        logger.debug("Failed to stop server '%s': %s", server_name, exc)

    return []


def _build_launch_command(manifest: dict[str, Any]) -> list[str] | None:
    """Build a command list to launch an installed server."""
    source_type = manifest.get("source_type", "")
    name = manifest.get("name", "")

    if source_type == "git":
        install_dir = Path.home() / ".mcp-pm" / "servers" / name
        # Try common entry points
        for entry in ("main.py", "src/main.py", "index.js", "server.py", "src/server.py"):
            candidate = install_dir / entry
            if candidate.exists():
                if candidate.suffix == ".py":
                    return [sys.executable, str(candidate)]
                elif candidate.suffix == ".js":
                    return ["node", str(candidate)]
        # Fallback: try package.json scripts
        pkg_json = install_dir / "package.json"
        if pkg_json.exists():
            return ["npx", "-y", str(install_dir)]
        return [sys.executable, "-m", name]

    if source_type == "pip":
        package = manifest.get("package", name)
        return [sys.executable, "-m", package]

    return None


# ---------------------------------------------------------------------------
# Main Click CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version="0.2.0", prog_name="mcp-pm")
def cli() -> None:
    """mcp-pm — Homebrew for MCP Servers."""
    pass
