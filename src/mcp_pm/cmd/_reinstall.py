# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""reinstall command — uninstall and install again (brew reinstall equivalent)."""

from __future__ import annotations

from pathlib import Path

import click

from mcp_pm.cmd._helpers import (
    _async_run,
    _get_installer,
    _print_error,
    _print_success,
    cli,
    console,
    escape,
)
from mcp_pm.registry import ServerManifest


@cli.command()
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def reinstall(name: str, yes: bool) -> None:
    """Reinstall a server (uninstall + install again).

    Preserves the formula.yaml during reinstallation.
    """
    try:
        installer = _get_installer()
        manifest = installer.get_manifest(name)
        if manifest is None:
            _print_error(f"Server '{name}' is not installed.")
            raise SystemExit(1)

        if not yes:
            console.print(f"Reinstall server: [bold]{escape(name)}[/bold]")
            click.confirm("Are you sure?", default=True, abort=True)

        # Backup formula.yaml
        formula_path = Path.home() / ".mcp-pm" / "servers" / name / "formula.yaml"
        formula_backup: str | None = None
        if formula_path.exists():
            formula_backup = formula_path.read_text(encoding="utf-8")

        console.print("[dim]Uninstalling...[/dim]")
        uninstall_ok = _async_run(installer.uninstall(name))
        if not uninstall_ok:
            _print_error(f"Failed to uninstall '{name}'.")
            raise SystemExit(1)

        # Restore formula.yaml
        if formula_backup is not None:
            formula_path.parent.mkdir(parents=True, exist_ok=True)
            formula_path.write_text(formula_backup, encoding="utf-8")

        console.print("[dim]Reinstalling...[/dim]")
        # Build ServerManifest from the original manifest dict
        install_manifest = ServerManifest(
            name=manifest.get("name", name),
            description=manifest.get("description", ""),
            source_type=manifest.get("source_type", "git"),
            source_url=manifest.get("source_url", ""),
            author=manifest.get("author"),
            homepage=manifest.get("homepage"),
            license=manifest.get("license"),
            stars=manifest.get("stars", 0),
            tags=manifest.get("tags", []),
            tools_count=manifest.get("tools_count", 0),
        )
        install_ok = _async_run(installer.install(install_manifest))
        if install_ok:
            _print_success(f"Reinstalled server '{name}'")
        else:
            _print_error(f"Failed to reinstall '{name}'.")
            raise SystemExit(1)

    except click.Abort:
        console.print("[yellow]Reinstall cancelled.[/yellow]")
        raise SystemExit(0) from None
    except Exception as exc:
        _print_error(f"Reinstall failed: {exc}")
        raise SystemExit(1) from exc
