# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""create command — scaffold a new formula.yaml template (brew create equivalent)."""

from __future__ import annotations

from pathlib import Path

import click
import yaml

from mcp_pm.cmd._helpers import _print_error, _print_success, cli, console, escape


@cli.command()
@click.argument("name")
@click.option("--description", "-d", help="Server description")
@click.option("--source-type", "-t", type=click.Choice(["git", "npm", "pip", "docker"]),
              default="git", help="Source type")
@click.option("--source-url", "-u", help="Source URL (git repo, npm package, etc.)")
@click.option("--homepage", help="Project homepage URL")
@click.option("--author", "-a", help="Author or organization")
@click.option("--output", "-o", help="Output directory (default: current directory)")
@click.option("--interactive", "-i", is_flag=True, help="Interactive prompts")
def create(
    name: str,
    description: str | None,
    source_type: str | None,
    source_url: str | None,
    homepage: str | None,
    author: str | None,
    output: str | None,
    interactive: bool,
) -> None:
    """Scaffold a new formula.yaml template for an MCP server."""
    try:
        if interactive:
            if not description:
                description = click.prompt("Description", default="")
            if not source_type:
                source_type = click.prompt("Source type", type=click.Choice(["git", "npm", "pip", "docker"]), default="git")
            if not source_url:
                source_url = click.prompt("Source URL", default="")
            if not homepage:
                homepage = click.prompt("Homepage", default="")
            if not author:
                author = click.prompt("Author", default="")

        out_dir = Path(output or ".").resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        formula_path = out_dir / "formula.yaml"

        formula_data = {
            "name": name,
            "description": description or "",
            "source_type": source_type or "git",
            "source_url": source_url or "",
            "version": "0.1.0",
            "pinned": False,
        }
        if homepage:
            formula_data["homepage"] = homepage
        if author:
            formula_data["author"] = author

        formula_path.write_text(
            yaml.dump(formula_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        _print_success(f"Created formula.yaml at {escape(str(formula_path))}")
        console.print("\n[dim]Edit this file to customize the formula, then run:[/dim]")
        console.print(f"  [bold]mcp install {escape(str(formula_path))}[/bold]")

    except Exception as exc:
        _print_error(f"Failed to create formula: {exc}")
        raise SystemExit(1) from exc
