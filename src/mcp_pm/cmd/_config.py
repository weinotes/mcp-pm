# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""config command — manage mcp-pm configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from mcp_pm.cmd._helpers import _get_config, _print_error, _print_success, cli, console, escape
from mcp_pm.exceptions import ConfigError


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
