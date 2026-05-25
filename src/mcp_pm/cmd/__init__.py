# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""Command package for mcp-pm CLI.

Each module registers its command(s) on the shared ``cli`` Click group
imported from :mod:`mcp_pm.cli`.
"""

from __future__ import annotations

# Import all command modules so they register on the cli group
from mcp_pm.cmd import (  # noqa: F401
    _audit,
    _autoremove,
    _bump,
    _cleanup,
    _completion,
    _config,
    _create,
    _deps,
    _doctor,
    _explore,
    _home,
    _info,
    _install,
    _leaves,
    _list,
    _log,
    _outdated,
    _pin,
    _reinstall,
    _run,
    _sandbox,
    _search,
    _serve,
    _services,
    _tap,
    _uninstall,
    _update,
)
