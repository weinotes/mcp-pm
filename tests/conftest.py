"""
Shared pytest fixtures for mcp-pm tests.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

import json
from pathlib import Path
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def tmp_home(tmp_path: Path) -> Path:
    """Create a temporary home directory for config/servers."""
    home = tmp_path / "home"
    home.mkdir(parents=True)
    (home / ".mcp-pm").mkdir()
    (home / ".mcp-pm" / "servers").mkdir()
    return home


@pytest.fixture
def sample_manifest() -> dict[str, Any]:
    """Return a sample MCP server manifest."""
    return {
        "name": "test-server",
        "description": "A test MCP server",
        "source_type": "git",
        "source_url": "https://github.com/test/test-mcp-server",
        "author": "Test Author",
        "license": "MIT",
        "stars": 42,
        "tags": ["test", "demo"],
        "tools_count": 3,
    }


@pytest.fixture
def mock_http_client() -> Generator[AsyncMock, None, None]:
    """Create a mock httpx AsyncClient."""
    client = AsyncMock(spec=["get", "post"])
    client.get.return_value = MagicMock(status_code=200)
    client.get.return_value.json.return_value = {"servers": []}
    client.post.return_value = MagicMock(status_code=200)
    client.post.return_value.json.return_value = {"result": "ok"}
    yield client


@pytest.fixture
def sample_tools_json() -> str:
    """Sample MCP tools/list response JSON."""
    return json.dumps({
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": "echo",
                    "description": "Echo back input",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                    },
                },
            ],
        },
        "id": 1,
    })
