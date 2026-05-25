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


# ── Mock McpRegistryBackend (no real HTTP) ──────────────────────────────


class MockMcpRegistry:
    """Simple mock that exposes _parse_server without real HTTP calls."""

    name = "mcp_registry"

    def _parse_server(self, raw: dict) -> object:
        from mcp_pm.registry.online import McpRegistryBackend
        from mcp_pm.registry.models import ServerManifest
        # Build a real backend instance and delegate (no HTTP calls involved)
        result = McpRegistryBackend(client=None)._parse_server(raw)
        return result


@pytest.mark.asyncio
async def test_mcp_registry_parse_server() -> None:
    """McpRegistryBackend parses server entries correctly."""
    backend = MockMcpRegistry()
    raw = {
        "name": "filesystem-server",
        "description": "Access filesystem via MCP",
        "repository": "https://github.com/modelcontextprotocol/filesystem",
        "author": "MCP Team",
        "tags": ["filesystem", "official"],
        "stars": 150,
        "tools_count": 5,
    }
    parsed = backend._parse_server(raw)
    assert parsed is not None
    assert parsed.name == "filesystem-server"
    assert parsed.source_type == "git"
    assert parsed.stars == 150
    assert parsed.tools_count == 5
    assert "filesystem" in parsed.tags


@pytest.mark.asyncio
async def test_mcp_registry_parse_server_pip() -> None:
    """McpRegistryBackend detects pip source type from command field."""
    backend = MockMcpRegistry()
    raw = {
        "name": "pip-server",
        "description": "Pip installed server",
        "command": "pip install my-server",
        "tags": ["python"],
    }
    parsed = backend._parse_server(raw)
    assert parsed is not None
    assert parsed.name == "pip-server"
    assert parsed.source_type == "pip"


@pytest.mark.asyncio
async def test_mcp_registry_parse_server_npm() -> None:
    """McpRegistryBackend detects npm source type."""
    backend = MockMcpRegistry()
    raw = {
        "name": "npm-server",
        "description": "NPM server",
        "command": "npx @org/mcp-server",
    }
    parsed = backend._parse_server(raw)
    assert parsed is not None
    assert parsed.source_type == "npm"


@pytest.mark.asyncio
async def test_mcp_registry_parse_server_empty_name() -> None:
    """McpRegistryBackend returns None for entries without name."""
    backend = MockMcpRegistry()
    assert backend._parse_server({}) is None
    assert backend._parse_server({"name": ""}) is None


@pytest.mark.asyncio
async def test_mcp_registry_parse_server_categories_as_tags() -> None:
    """McpRegistryBackend handles categories field as tags."""
    backend = MockMcpRegistry()
    raw = {
        "name": "cat-server",
        "categories": ["database", "sql"],
    }
    parsed = backend._parse_server(raw)
    assert parsed is not None
    assert "database" in parsed.tags
    assert "sql" in parsed.tags
