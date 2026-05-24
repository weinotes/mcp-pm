"""
Tests for the registry client.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

import pytest

from mcp_pm.registry import CompositeRegistry, ServerManifest


class MockRegistryBackend:
    """Simple mock registry for testing."""

    def __init__(self, servers: list[ServerManifest] | None = None) -> None:
        self.servers = servers or []

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:  # noqa: ARG002
        return self.servers[:limit]

    async def get(self, name: str) -> ServerManifest | None:
        for s in self.servers:
            if s.name == name:
                return s
        return None


@pytest.mark.asyncio
async def test_composite_registry_search() -> None:
    """Composite registry aggregates results from backends."""
    s1 = ServerManifest(name="test-server", description="A test MCP server", source_type="git", source_url="https://a")
    s2 = ServerManifest(name="another-test", description="Another test server", source_type="pip", source_url="https://b")
    backend = MockRegistryBackend([s1, s2])
    registry = CompositeRegistry([backend])

    results = await registry.search("test")
    assert len(results) == 2
    assert results[0].name == "test-server"


@pytest.mark.asyncio
async def test_composite_registry_get() -> None:
    """Composite registry finds by name across backends."""
    s1 = ServerManifest(name="target", description="Found", source_type="git", source_url="https://t")
    backend = MockRegistryBackend([s1])
    registry = CompositeRegistry([backend])

    result = await registry.get("target")
    assert result is not None
    assert result.name == "target"


@pytest.mark.asyncio
async def test_composite_registry_get_missing() -> None:
    """Composite registry returns None for unknown names."""
    registry = CompositeRegistry([MockRegistryBackend()])
    result = await registry.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_composite_registry_empty_backends() -> None:
    """Empty backends list returns empty results."""
    registry = CompositeRegistry([])
    results = await registry.search("test")
    assert results == []
