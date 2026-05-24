# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""Data models for the registry system."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ServerManifest:
    """Metadata for an MCP server in the registry."""

    name: str
    description: str
    source_type: str  # git, npm, pip, docker
    source_url: str
    author: str | None = None
    homepage: str | None = None
    license: str | None = None
    stars: int = 0
    tags: list[str] = field(default_factory=list)
    tools_count: int = 0
