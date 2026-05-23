# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""
CLI entry point for mcp-pm.

Defines the Click command group and all 12 subcommands:
  install, uninstall, list, search, info, explore,
  serve, config, sandbox, doctor, run, update.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import click
from rich.box import MINIMAL, ROUNDED
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
from rich.text import Text
from rich.tree import Tree

from mcp_pm.client import MCPSession
from mcp_pm.config import Config
from mcp_pm.exceptions import (
    ConfigError,
    InstallError,
    McpPmError,
    SandboxError,
)
from mcp_pm.installer import Installer
from mcp_pm.registry import RegistryManager, ServerManifest
from mcp_pm.sandbox import SandboxLevel
from mcp_pm.server import start as start_proxy_server

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
# Shared helpers
# ---------------------------------------------------------------------------

console = Console()


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
    console.print(f"[red]✗[/red] {escape(msg)}")


def _print_success(msg: str) -> None:
    console.print(f"[green]✓[/green] {escape(msg)}")


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


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version="0.1.0", prog_name="mcp-pm")
def cli() -> None:
    """mcp-pm — Homebrew for MCP Servers."""
    pass


# ---------------------------------------------------------------------------
# 1. install
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("source")
@click.option("--name", "-n", help="Custom name for the installed server")
@click.option(
    "--from",
    "source_type",
    type=click.Choice(["git", "npm", "pip", "docker"]),
    help="Source type (auto-detected if omitted)",
)
@click.option("--version", "-v", help="Specific version to install")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def install(
    source: str,
    name: str | None,
    source_type: str | None,
    version: str | None,
    yes: bool,
) -> None:
    """Install an MCP server from a registry, git repo, or package source."""
    try:
        if not yes:
            console.print(f"Preparing to install: [bold]{escape(source)}[/bold]")
            click.confirm("Continue?", default=True, abort=True)

        # Auto-detect source type if not provided
        detected_type = source_type
        if detected_type is None:
            detected_type = _detect_source_type(source)

        with _create_progress(f"Installing {source}...") as progress:
            task = progress.add_task("Installing...", total=None)

            installer = _get_installer()

            # Build ServerManifest from source
            server_name = name or _derive_name(source)
            manifest = ServerManifest(
                name=server_name,
                description=f"Installed from {source}",
                source_type=detected_type or "git",
                source_url=source,
            )

            success = _async_run(installer.install(manifest))
            progress.update(task, completed=True)

        if success:
            _print_success(f"Installed server '{server_name}' from {source}")
            # Show installed metadata
            meta = installer.get_manifest(server_name)
            if meta:
                _show_server_brief(meta)
        else:
            _print_error(f"Failed to install '{server_name}'. Already installed or invalid source.")

    except McpPmError as exc:
        _print_error(str(exc))
        raise SystemExit(1) from exc
    except click.Abort:
        console.print("[yellow]Installation cancelled.[/yellow]")
        raise SystemExit(0) from None
    except Exception as exc:
        _print_error(f"Unexpected error: {exc}")
        raise SystemExit(1) from exc


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


# ---------------------------------------------------------------------------
# 2. uninstall
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def uninstall(name: str, yes: bool) -> None:
    """Uninstall an MCP server by name."""
    try:
        if not yes:
            console.print(f"Uninstall server: [bold]{escape(name)}[/bold]")
            click.confirm("Are you sure?", default=False, abort=True)

        installer = _get_installer()
        success = _async_run(installer.uninstall(name))

        if success:
            _print_success(f"Uninstalled server '{name}'")
        else:
            _print_error(f"Server '{name}' is not installed.")

    except click.Abort:
        console.print("[yellow]Uninstall cancelled.[/yellow]")
        raise SystemExit(0) from None
    except Exception as exc:
        _print_error(f"Uninstall failed: {exc}")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# 3. list
# ---------------------------------------------------------------------------


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
            tree = Tree("📦 [bold]MCP Servers[/bold]")
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
    except Exception:
        pass

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
# 4. search
# ---------------------------------------------------------------------------


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

        # Sort by stars descending
        results.sort(key=lambda m: m.stars, reverse=True)

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


# ---------------------------------------------------------------------------
# 5. info
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("name")
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def info(name: str, json_out: bool) -> None:
    """Show detailed info about an installed or registry MCP server."""
    try:
        # First check if installed
        installer = _get_installer()
        manifest = installer.get_manifest(name)

        if manifest:
            if json_out:
                console.print_json(data=manifest)
                return

            table = Table(box=MINIMAL, show_header=False, title=f"Server: {name}")
            table.add_column("Key", style="bold cyan", width=18)
            table.add_column("Value")

            for k, v in manifest.items():
                if k == "path":
                    continue
                table.add_row(str(k), escape(str(v)))

            console.print(Panel(table, border_style="cyan"))
            return

        # Check registry
        reg = _get_registry()
        with _create_progress(f"Looking up '{name}'...") as progress:
            task = progress.add_task("Querying...", total=None)
            remote = _async_run(reg.get(name))
            progress.update(task, completed=True)

        if remote is None:
            _print_error(f"Server '{name}' not found locally or in registries.")
            raise SystemExit(1)

        if json_out:
            console.print_json(data=remote.__dict__)
            return

        # Display remote info
        table = Table(box=MINIMAL, show_header=False, title=f"Registry: {name}")
        table.add_column("Key", style="bold cyan", width=18)
        table.add_column("Value")
        table.add_row("Name", escape(remote.name))
        table.add_row("Description", escape(remote.description))
        table.add_row("Source Type", remote.source_type)
        table.add_row("Source URL", escape(remote.source_url))
        table.add_row("Author", escape(remote.author or "-"))
        table.add_row("Homepage", escape(remote.homepage or "-"))
        table.add_row("License", escape(remote.license or "-"))
        table.add_row("Stars", str(remote.stars))
        table.add_row("Tools Count", str(remote.tools_count))
        if remote.tags:
            table.add_row("Tags", ", ".join(remote.tags))

        console.print(Panel(table, border_style="cyan"))

    except Exception as exc:
        _print_error(f"Info lookup failed: {exc}")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# 6. explore
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--port", "-p", default=8080, help="Dashboard port", type=int)
@click.option("--open", "open_browser", is_flag=True, help="Auto-open browser")
def explore(port: int, open_browser: bool) -> None:
    """Start the Web UI dashboard in a browser."""
    try:
        import uvicorn

        from mcp_pm.webui.app import app

        url = f"http://127.0.0.1:{port}"
        console.print(f"[green]Starting mcp-pm Dashboard at {url} ...[/green]")

        if open_browser:
            import webbrowser

            webbrowser.open(url)

        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

    except ImportError as exc:
        _print_error(f"Missing dependency: {exc}. Install with: pip install 'mcp-pm[web]'")
        raise SystemExit(1) from exc
    except Exception as exc:
        _print_error(f"Failed to start dashboard: {exc}")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# 7. serve
# ---------------------------------------------------------------------------

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
                        progress.update(task, completed=True, description=f"[green]✓ {name}[/green]")
                    else:
                        _print_error(f"  Cannot launch server '{name}': unknown command")
                        progress.update(task, completed=True, description=f"[red]✗ {name}[/red]")
                except Exception as exc:
                    _print_error(f"  Failed to start '{name}': {exc}")
                    progress.update(task, completed=True, description=f"[red]✗ {name}[/red]")

        if len(session.servers) == 0:
            _print_error("No servers could be started.")
            raise SystemExit(1)

        _session_for_serve = session
        console.print(
            f"[green]✓ Started {len(session.servers)} server(s) with "
            f"{len(session.get_all_tools())} tool(s)[/green]"
        )

        if not openai:
            console.print("[yellow]Note: --openai not set. Using default proxy mode.[/yellow]")

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


# ---------------------------------------------------------------------------
# 8. config
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("action", type=click.Choice(["get", "set", "export", "import"]))
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(action: str, key: str | None, value: str | None) -> None:
    """Manage mcp-pm configuration (get/set/export/import)."""
    try:
        cfg = _get_config()

        if action == "get":
            if not key:
                _print_error("Usage: mcp config get <key>")
                raise SystemExit(1)
            val = cfg.get(key)
            if val is None:
                console.print(f"[yellow]Key '{key}' not found.[/yellow]")
            else:
                console.print(escape(str(val)))

        elif action == "set":
            if not key or value is None:
                _print_error("Usage: mcp config set <key> <value>")
                raise SystemExit(1)
            # Try parsing as int/float/bool
            parsed: Any = value
            if value.lower() in ("true", "false"):
                parsed = value.lower() == "true"
            else:
                try:
                    parsed = int(value)
                except ValueError:
                    try:
                        parsed = float(value)
                    except ValueError:
                        parsed = value
            cfg.set(key, parsed)
            cfg.save()
            _print_success(f"Set config {key} = {parsed}")

        elif action == "export":
            output = cfg.export()
            console.print(output.strip() if output.strip() else "[dim](empty config)[/dim]")

        elif action == "import":
            if not key:
                _print_error("Usage: mcp config import <yaml_file_path>")
                raise SystemExit(1)
            import_path = Path(key)
            if not import_path.exists():
                _print_error(f"File not found: {import_path}")
                raise SystemExit(1)
            yaml_content = import_path.read_text(encoding="utf-8")
            cfg.import_str(yaml_content)
            cfg.save()
            _print_success(f"Imported config from {import_path}")

    except ConfigError as exc:
        _print_error(str(exc))
        raise SystemExit(1) from exc
    except Exception as exc:
        _print_error(f"Config operation failed: {exc}")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# 9. sandbox
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 10. doctor
# ---------------------------------------------------------------------------


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
            icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
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


# ---------------------------------------------------------------------------
# 11. run
# ---------------------------------------------------------------------------


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
            progress.update(task, completed=True, description=f"[green]✓ {server}[/green]")

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


# ---------------------------------------------------------------------------
# 12. update
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def update(yes: bool) -> None:
    """Update all installed MCP servers to latest versions."""
    try:
        installer = _get_installer()
        servers = installer.list_installed()

        if not servers:
            console.print("[yellow]No servers installed to update.[/yellow]")
            return

        names = [s.get("name", "?") for s in servers]

        if not yes:
            console.print(f"Servers to update: [bold]{', '.join(escape(n) for n in names)}[/bold]")
            click.confirm("Proceed with update?", default=True, abort=True)

        results: list[tuple[str, bool]] = []

        with _create_progress("Updating servers...") as progress:
            for name in names:
                task = progress.add_task(f"Updating {name}...", total=None)
                try:
                    ok = _async_run(installer.update(name))
                    results.append((name, ok))
                    progress.update(
                        task,
                        completed=True,
                        description=f"[{'green' if ok else 'red'}]{'✓' if ok else '✗'} {name}[/{'green' if ok else 'red'}]",
                    )
                except InstallError as exc:
                    results.append((name, False))
                    progress.update(
                        task,
                        completed=True,
                        description=f"[red]✗ {name} ({escape(str(exc))})[/red]",
                    )

        # Summary
        success_count = sum(1 for _, ok in results if ok)
        fail_count = len(results) - success_count

        if fail_count == 0:
            _print_success(f"All {success_count} server(s) updated successfully.")
        else:
            console.print(
                f"[yellow]{success_count} updated, {fail_count} failed:[/yellow]"
            )
            for name, ok in results:
                if not ok:
                    console.print(f"  [red]✗[/red] {escape(name)}")

    except click.Abort:
        console.print("[yellow]Update cancelled.[/yellow]")
        raise SystemExit(0) from None
    except Exception as exc:
        _print_error(f"Update failed: {exc}")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
