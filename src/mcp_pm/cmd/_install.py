# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""install command — install an MCP server from a registry, git repo, or package source."""

from __future__ import annotations

import click

from mcp_pm.cmd._helpers import (
    _async_run,
    _create_progress,
    _derive_name,
    _detect_source_type,
    _get_installer,
    _print_error,
    _print_success,
    _show_server_brief,
    cli,
    console,
    escape,
)
from mcp_pm.exceptions import McpPmError
from mcp_pm.registry import ServerManifest


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
            from sys import stdin

            if not stdin.isatty():
                # Non-interactive mode: auto-proceed
                console.print(f"Installing: [bold]{escape(source)}[/bold] (non-interactive)")
            else:
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
