# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""explore command — start the Web UI dashboard in a browser."""

from __future__ import annotations

import click

from mcp_pm.cmd._helpers import _print_error, cli, console


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
