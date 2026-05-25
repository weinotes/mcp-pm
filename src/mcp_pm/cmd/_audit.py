# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""audit command — check formula quality for installed MCP servers."""

from __future__ import annotations

import click
from rich.panel import Panel

from mcp_pm.cmd._helpers import _print_error, cli, console, escape


@cli.command()
@click.argument("name", required=False)
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
@click.option("--fix", is_flag=True, help="Auto-fix minor issues")
def audit(name: str | None, json_out: bool, fix: bool) -> None:
    """Check formula quality for installed MCP servers.

    Audits all servers, or a specific server by NAME.
    """
    from mcp_pm.audit import audit_all, audit_server

    try:
        results = [audit_server(name)] if name else audit_all()

        if not results:
            console.print("[yellow]No servers to audit.[/yellow]")
            return

        if json_out:
            output = []
            for r in results:
                output.append({
                    "name": r.name,
                    "passed": r.passed,
                    "issues": [
                        {"severity": i.severity, "check": i.check, "message": i.message}
                        for i in r.issues
                    ],
                })
            console.print_json(data=output)
            return

        total_errors = 0
        total_warnings = 0
        for r in results:
            if r.passed and not r.issues:
                continue
            total_errors += r.error_count
            total_warnings += r.warning_count

            header_style = "red" if r.error_count > 0 else "yellow"
            parts = []
            if r.error_count:
                parts.append(f"[red]{r.error_count} error(s)[/red]")
            if r.warning_count:
                parts.append(f"[yellow]{r.warning_count} warning(s)[/yellow]")
            summary = " ".join(parts)
            console.print(Panel(
                f"[bold]{escape(r.name)}[/bold] {summary}",
                border_style=header_style,
            ))
            for issue in r.issues:
                icon = "[red]\u2717[/red]" if issue.severity == "error" else \
                       "[yellow]\u26a0[/yellow]" if issue.severity == "warning" else \
                       "[dim]\u2139[/dim]"
                console.print(f"  {icon} [{issue.severity}] {escape(issue.message)}")

        # Summary
        if not any(r.issues for r in results):
            total = len(results)
            console.print(f"\n[green]All {total} server(s) passed audit![/green]")
        else:
            console.print(
                f"\n[dim]{total_errors} error(s), {total_warnings} warning(s) "
                f"across {len(results)} server(s)[/dim]"
            )

    except Exception as exc:
        _print_error(f"Audit failed: {exc}")
        raise SystemExit(1) from exc
