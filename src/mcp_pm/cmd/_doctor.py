# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""doctor command — check the health of your mcp-pm installation and MCP servers."""

from __future__ import annotations

import sys
from pathlib import Path

from rich.panel import Panel
from rich.text import Text

from mcp_pm.cmd._helpers import (
    _LOG_FILE,
    _async_run,
    _get_installer,
    _get_registry,
    _print_error,
    cli,
    console,
)


@cli.command()
def doctor() -> None:
    """Check the health of your mcp-pm installation and MCP servers."""
    try:
        checks: list[tuple[str, bool, str]] = []

        # Python version
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        py_ok = sys.version_info >= (3, 10)
        checks.append(("Python version", py_ok, f"{py_ver} ({'>= 3.10' if py_ok else '< 3.10, may have issues'})"))

        # mcp-pm version
        try:
            from importlib.metadata import version as _ver

            pm_ver = _ver("mcp-pm")
            checks.append(("mcp-pm version", True, pm_ver))
        except Exception:
            checks.append(("mcp-pm version", False, "unknown"))

        # Config directory
        config_dir = Path.home() / ".mcp-pm"
        config_ok = config_dir.exists()
        checks.append(("Config directory", config_ok, str(config_dir) + (" (exists)" if config_ok else " (missing)")))

        # Installed servers
        installer = _get_installer()
        servers = installer.list_installed()
        srv_ok = len(servers) > 0
        srv_msg = f"{len(servers)} server(s) installed"
        if servers:
            names = ", ".join(s.get("name", "?") for s in servers)
            srv_msg += f": {names}"
        checks.append(("Installed servers", srv_ok, srv_msg))

        # Network connectivity (try to reach registry)
        try:
            reg = _get_registry()
            _async_run(reg.search("mcp", limit=1))
            checks.append(("Network connectivity", True, "Registry reachable"))
        except Exception as exc:
            checks.append(("Network connectivity", False, f"Registry unreachable: {exc}"))

        # Log file
        log_ok = _LOG_FILE.exists()
        log_size = _LOG_FILE.stat().st_size if log_ok else 0
        checks.append(("Log file", log_ok, str(_LOG_FILE) + (f" ({log_size} bytes)" if log_ok else " (not found)")))

        # Display checks as panels
        for label, ok, detail in checks:
            icon = "[green]\u2713[/green]" if ok else "[red]\u2717[/red]"
            status = Text.assemble(
                (icon, ""),
                " ",
                (label, "bold"),
                ": ",
                (detail, ""),
            )
            border_style = "green" if ok else "red"
            console.print(Panel(status, border_style=border_style))

        # Summary
        passed = sum(1 for _, ok, _ in checks if ok)
        total = len(checks)
        if passed == total:
            console.print(f"\n[green]All {total} checks passed![/green]")
        else:
            console.print(f"\n[yellow]{passed}/{total} checks passed. {total - passed} issue(s) found.[/yellow]")

    except Exception as exc:
        _print_error(f"Doctor check failed: {exc}")
        raise SystemExit(1) from exc
