# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""completion command — generate shell completion script."""

from __future__ import annotations

import click

from mcp_pm.cmd._helpers import cli, console


@cli.command()
@click.argument("shell", type=click.Choice(["zsh", "bash", "fish"]), default="zsh")
def completion(shell: str) -> None:
    """Generate shell completion script.

    Usage:

        eval "$(mcp completion zsh)"   # zsh
        eval "$(mcp completion bash)"  # bash
        mcp completion fish > ~/.config/fish/completions/mcp.fish  # fish
    """
    import click.shell_completion

    cls_map = {
        "zsh": click.shell_completion.ZshComplete,
        "bash": click.shell_completion.BashComplete,
        "fish": click.shell_completion.FishComplete,
    }
    comp = cls_map[shell](cli, {}, "mcp", "")
    console.print(comp.source())
