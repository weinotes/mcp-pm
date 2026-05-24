# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""Registry package — discovers MCP servers from multiple backends."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx

from mcp_pm.registry.base import RegistryBackend
from mcp_pm.registry.builtin import BuiltInBackend
from mcp_pm.registry.models import ServerManifest
from mcp_pm.registry.online import (
    GitHubRegistryBackend,
    McpSoBackend,
    NpmRegistryBackend,
    PyPIRegistryBackend,
    SmitheryBackend,
)
from mcp_pm.registry.tap_backend import TapRegistryBackend

logger = logging.getLogger(__name__)


class CompositeRegistry:
    """Aggregates multiple registry backends."""

    def __init__(self, backends: list[RegistryBackend] | None = None) -> None:
        self.backends = backends or []

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search across all backends in parallel, deduplicated by name.

        Filters results by relevance — only items containing at least one
        query word as a whole word in name, description, or author are kept.
        """
        query_words = {w.lower() for w in query.split() if w.strip()}
        seen: set[str] = set()
        results: list[ServerManifest] = []

        async def _search_one(backend: RegistryBackend) -> list[ServerManifest]:
            try:
                return await asyncio.wait_for(
                    backend.search(query, limit),
                    timeout=3.0,
                )
            except Exception:
                return []

        batches = await asyncio.gather(
            *[_search_one(b) for b in self.backends],
            return_exceptions=False,
        )
        for batch in batches:
            for item in batch:
                if item.name not in seen:
                    seen.add(item.name)
                    # Relevance filter: at least one query word must appear as
                    # a whole word in name, description, or author
                    if query_words and not BuiltInBackend._is_relevant(item.name, query_words) \
                       and not BuiltInBackend._is_relevant(item.description or "", query_words) \
                       and not BuiltInBackend._is_relevant(item.author or "", query_words):
                        continue
                    results.append(item)
        return results[:limit]

    async def get(self, name: str) -> ServerManifest | None:
        """Get a server by name across all backends in parallel, return first match."""
        async def _get_one(backend: RegistryBackend) -> ServerManifest | None:
            try:
                return await asyncio.wait_for(
                    backend.get(name),
                    timeout=3.0,
                )
            except Exception:
                return None

        for result in await asyncio.gather(
            *[_get_one(b) for b in self.backends],
            return_exceptions=False,
        ):
            if result is not None:
                return result
        return None

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        """Get popular servers across all backends in parallel, deduplicated."""
        seen: set[str] = set()
        results: list[ServerManifest] = []

        async def _popular_one(backend: RegistryBackend) -> list[ServerManifest]:
            try:
                return await asyncio.wait_for(
                    backend.popular(limit),
                    timeout=3.0,
                )
            except Exception:
                return []

        batches = await asyncio.gather(
            *[_popular_one(b) for b in self.backends],
            return_exceptions=False,
        )
        for batch in batches:
            for item in batch:
                if item.name not in seen:
                    seen.add(item.name)
                    results.append(item)
        return results[:limit]


class RegistryManager:
    """High-level manager that aggregates all registry backends.

    Provides unified search, get, and popular interfaces.
    Auto-creates the default backends if none are provided.
    """

    def __init__(
        self,
        backends: list[RegistryBackend] | None = None,
        client: httpx.AsyncClient | None = None,
        extra_catalog_paths: list[Path] | None = None,
    ) -> None:
        """Initialize with optional custom backends and HTTP client.

        If no backends are given, creates the default backends:
        BuiltIn, MCP.so, GitHub Registry, Smithery, npm, PyPI.

        Args:
            backends: Custom backend list (overrides defaults).
            client: Shared HTTP client for network backends.
            extra_catalog_paths: Additional YAML files to merge into BuiltInBackend.
        """
        self._client = client
        self._extra_catalog_paths = extra_catalog_paths
        if backends:
            self.backends = backends
        else:
            self.backends = [
                BuiltInBackend(extra_paths=extra_catalog_paths),
                TapRegistryBackend(),
                McpSoBackend(client=client),
                GitHubRegistryBackend(client=client),
                SmitheryBackend(client=client),
                NpmRegistryBackend(client=client),
                PyPIRegistryBackend(client=client),
            ]
        self._composite = CompositeRegistry(self.backends)

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search for MCP servers across all backends."""
        return await self._composite.search(query, limit)

    async def get(self, name: str) -> ServerManifest | None:
        """Get detailed info about a specific MCP server."""
        return await self._composite.get(name)

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        """Get popular MCP servers across all backends."""
        return await self._composite.popular(limit)

    async def close(self) -> None:
        """Close the underlying HTTP client if we own it."""
        if self._client is not None:
            await self._client.aclose()

    async def __aenter__(self) -> RegistryManager:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
