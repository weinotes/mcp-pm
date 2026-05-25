# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""bump command — update the version field in formula.yaml (brew bump equivalent)."""

from __future__ import annotations

import click

from mcp_pm.cmd._helpers import (
    _async_run,
    _print_error,
    _print_success,
    cli,
    console,
    logger,
)
from mcp_pm.formula import FormulaManager


@cli.command()
@click.argument("name")
@click.argument("version", required=False)
def bump(name: str, version: str | None) -> None:
    """Update the version of a formula.

    If VERSION is provided, writes it directly.
    If omitted, auto-detects the latest version from the remote source.
    """
    try:
        fm = FormulaManager()
        formula = fm.load(name)
        if formula is None:
            _print_error(f"Server '{name}' is not installed.")
            raise SystemExit(1)

        old_version = formula.version

        if version:
            new_version = version
        else:
            console.print(f"[dim]Auto-detecting latest version for '{name}'...[/dim]")
            new_version = _async_run(fm.check_latest(formula))
            if new_version is None:
                _print_error(f"Could not auto-detect latest version for '{name}'.")
                raise SystemExit(1)

        formula.version = new_version
        fm.save(formula)
        logger.info("Bumped %s from %s to %s", name, old_version, new_version)
        _print_success(f"Bumped '{name}' from {old_version} to {new_version}")

    except Exception as exc:
        _print_error(f"Failed to bump version: {exc}")
        raise SystemExit(1) from exc
