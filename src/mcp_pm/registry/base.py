# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""Base classes for registry backends."""
from __future__ import annotations

from abc import ABC, abstractmethod

from mcp_pm.registry.models import ServerManifest


class RegistryBackend(ABC):
    """Abstract base for registry backend implementations."""

    name: str = "base"

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search servers matching query."""
        ...

    @abstractmethod
    async def get(self, name: str) -> ServerManifest | None:
        """Get a single server by name."""
        ...

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        """Return popular/hot servers. Defaults to empty list."""
        return []
