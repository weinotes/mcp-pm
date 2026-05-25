# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""update command — update all installed MCP servers to latest versions."""

from __future__ import annotations

import click

from mcp_pm.cmd._helpers import (
    _async_run,
    _create_progress,
    _get_installer,
    _print_error,
    _print_success,
    cli,
    console,
    escape,
)
from mcp_pm.exceptions import InstallError


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
                        description=f"[{'green' if ok else 'red'}]{chr(0x2713) if ok else chr(0x2717)} {name}[/{'green' if ok else 'red'}]",
                    )
                except InstallError as exc:
                    results.append((name, False))
                    progress.update(
                        task,
                        completed=True,
                        description=f"[red]\u2717 {name} ({escape(str(exc))})[/red]",
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
                    console.print(f"  [red]\u2717[/red] {escape(name)}")

    except click.Abort:
        console.print("[yellow]Update cancelled.[/yellow]")
        raise SystemExit(0) from None
    except Exception as exc:
        _print_error(f"Update failed: {exc}")
        raise SystemExit(1) from exc
