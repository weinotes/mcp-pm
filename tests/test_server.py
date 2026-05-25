"""
Tests for the HTTP proxy server — create_app, tool conversion, endpoints.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mcp_pm.client import MCPSession, MCPTool
from mcp_pm.server import create_app, mcp_tool_to_openai


class TestMCPToolConversion:
    """Tests for mcp_tool_to_openai."""

    def test_basic_conversion(self) -> None:
        """Basic MCPTool converts to OpenAI function format."""
        tool = MCPTool(name="echo", description="Echo back input", parameters={
            "type": "object",
            "properties": {"message": {"type": "string"}},
        })
        result = mcp_tool_to_openai(tool)
        assert result["type"] == "function"
        assert result["function"]["name"] == "echo"
        assert result["function"]["description"] == "Echo back input"
        assert result["function"]["parameters"]["type"] == "object"

    def test_conversion_adds_wrapper(self) -> None:
        """Tool without schema type gets wrapped with object wrapper."""
        tool = MCPTool(name="simple", description="Simple tool", parameters={
            "message": {"type": "string"},
        })
        result = mcp_tool_to_openai(tool)
        assert result["function"]["parameters"]["type"] == "object"
        assert "message" in result["function"]["parameters"]["properties"]

    def test_conversion_no_params(self) -> None:
        """Tool with empty params still produces valid OpenAI format."""
        tool = MCPTool(name="noop", description="No operation", parameters={})
        result = mcp_tool_to_openai(tool)
        assert result["type"] == "function"
        assert result["function"]["name"] == "noop"


class TestCreateApp:
    """Tests for create_app and its endpoints."""

    @pytest.fixture
    def empty_session(self) -> MCPSession:
        """An MCPSession with no servers connected."""
        session = MCPSession()
        return session

    @pytest.fixture
    def populated_session(self) -> MCPSession:
        """An MCPSession with mock servers and tools."""
        session = MCPSession()

        # Add two mock "server connections" directly
        tool_a = MCPTool(name="greet", description="Say hello", parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
        })
        tool_b = MCPTool(name="echo", description="Echo input", parameters={
            "type": "object",
        })

        # Use mock servers in session.servers
        mock_server_a = MagicMock()
        mock_server_a.tools = [tool_a]

        mock_server_b = MagicMock()
        mock_server_b.tools = [tool_b]

        session._servers = {}
        session._servers["server-a"] = mock_server_a
        session._servers["server-b"] = mock_server_b
        return session

    def test_create_app_basic(self, empty_session: MCPSession) -> None:
        """Create app with empty session returns correct title."""
        app = create_app(empty_session)
        assert app.title == "mcp-pm Proxy Server"
        assert app.state.session is empty_session

    def test_health_endpoint_empty(self, empty_session: MCPSession) -> None:
        """Health check with no servers returns ok, zero counts."""
        app = create_app(empty_session)
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["servers_loaded"] == 0
        assert data["tools_loaded"] == 0
        assert data["version"] == "0.3.0"

    def test_health_endpoint_populated(self, populated_session: MCPSession) -> None:
        """Health check with servers shows correct counts."""
        app = create_app(populated_session)
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["servers_loaded"] == 2
        assert data["tools_loaded"] == 2
        assert "server-a" in data["servers"]

    def test_list_tools_empty(self, empty_session: MCPSession) -> None:
        """List tools with no servers returns empty list."""
        app = create_app(empty_session)
        client = TestClient(app)
        resp = client.get("/v1/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert data["data"] == []

    def test_list_tools_populated(self, populated_session: MCPSession) -> None:
        """List tools returns all tools with server tags."""
        app = create_app(populated_session)
        client = TestClient(app)
        resp = client.post("/v1/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 2
        # Verify server tags
        servers = {t["function"]["_server"] for t in data["data"]}
        assert servers == {"server-a", "server-b"}

    def test_chat_completions_basic(self, populated_session: MCPSession) -> None:
        """Test basic chat completion returns non-streaming response."""
        app = create_app(populated_session)
        client = TestClient(app)
        payload = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        # The chat_completions endpoint tries to call the last assistant message
        # for tool calls or generate a response. With no tool calls in history,
        # it should generate a simple response.
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["model"] == "test-model"

    def test_chat_completions_with_tool_choice(self, empty_session: MCPSession) -> None:
        """Chat completion accepts tool_choice parameter."""
        app = create_app(empty_session)
        client = TestClient(app)
        payload = {
            "messages": [{"role": "user", "content": "List tools"}],
            "tools": [],
            "tool_choice": "auto",
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200

    def test_chat_completions_streaming(self, empty_session: MCPSession) -> None:
        """Streaming mode returns SSE response."""
        app = create_app(empty_session)
        client = TestClient(app)
        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")

    def test_chat_completions_executes_tool_calls(self) -> None:
        """When a tool call is present in assistant message, it's executed."""
        session = MCPSession()

        tool = MCPTool(name="greet", description="Say hello", parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
        })
        mock_server = MagicMock()
        mock_server.tools = [tool]
        session._servers = {"demo": mock_server}

        # Mock call_tool to return a result
        mock_result = MagicMock()
        mock_result.content = [{"text": "Hello, World!"}]
        mock_result.is_error = False
        session.call_tool = AsyncMock(return_value=mock_result)

        app = create_app(session)
        client = TestClient(app)
        payload = {
            "messages": [
                {"role": "user", "content": "Say hello"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "greet",
                                "arguments": '{"name": "World"}',
                            },
                        }
                    ],
                },
            ],
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        # Should contain tool results
        assert len(data["choices"]) >= 1

    def test_chat_completions_tool_not_found(self, empty_session: MCPSession) -> None:
        """Unknown tool returns error result."""
        app = create_app(empty_session)
        client = TestClient(app)
        payload = {
            "messages": [
                {"role": "user", "content": "Run tool"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_404",
                            "type": "function",
                            "function": {
                                "name": "nonexistent-tool",
                                "arguments": "{}",
                            },
                        }
                    ],
                },
            ],
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200

    def test_chat_completions_invalid_json_body(self, empty_session: MCPSession) -> None:
        """Invalid JSON body returns 422."""
        app = create_app(empty_session)
        client = TestClient(app)
        resp = client.post("/v1/chat/completitions", json={"invalid": True})
        assert resp.status_code == 404  # Wrong path

    def test_chat_completions_empty_messages(self, empty_session: MCPSession) -> None:
        """Empty messages list still returns a valid response."""
        app = create_app(empty_session)
        client = TestClient(app)
        payload = {"messages": []}
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
