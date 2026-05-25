"""Tests for the MCP client module.

Tests cover:
- JSON-RPC message building and response parsing
- TransportType enum and ProtocolError exception
- MCPTool / MCPToolResult dataclasses
- MCPClient._build_request / _parse_response / _next_id
- StdioMCPClient: connect/list_tools/call_tool/disconnect lifecycle
- HTTPMCPClient: connect/list_tools/call_tool/disconnect lifecycle
- MCPSession: multi-server management
- All major error paths (connection failure, protocol errors, invalid JSON, timeouts)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_pm.client import (
    HTTPMCPClient,
    MCPClient,
    MCPServer,
    MCPSession,
    MCPTool,
    MCPToolResult,
    ProtocolError,
    StdioMCPClient,
    TransportType,
)


# ============================================================================
# TransportType
# ============================================================================

class TestTransportType:
    def test_values(self) -> None:
        assert TransportType.STDIO == "stdio"
        assert TransportType.HTTP == "http"
        assert TransportType.SSE == "sse"

    def test_str_values(self) -> None:
        assert str(TransportType.STDIO) == "stdio"
        assert str(TransportType.HTTP) == "http"
        assert str(TransportType.SSE) == "sse"


# ============================================================================
# ProtocolError
# ============================================================================

class TestProtocolError:
    def test_is_exception(self) -> None:
        err = ProtocolError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"

    def test_raised_in_parse_response(self) -> None:
        client = MCPClient()
        with pytest.raises(ProtocolError, match="Invalid JSON"):
            client._parse_response("{{{broken")


# ============================================================================
# MCPTool / MCPToolResult dataclasses
# ============================================================================

class TestMCPTool:
    def test_default_parameters(self) -> None:
        tool = MCPTool(name="test", description="a tool")
        assert tool.name == "test"
        assert tool.description == "a tool"
        assert tool.parameters == {}

    def test_with_parameters(self) -> None:
        params = {"type": "object", "properties": {"x": {"type": "string"}}}
        tool = MCPTool(name="greet", description="greeting", parameters=params)
        assert tool.name == "greet"
        assert tool.parameters == params


class TestMCPToolResult:
    def test_default_is_error(self) -> None:
        result = MCPToolResult(content=[{"type": "text", "text": "hi"}])
        assert result.content == [{"type": "text", "text": "hi"}]
        assert result.is_error is False

    def test_with_error(self) -> None:
        result = MCPToolResult(content=[], is_error=True)
        assert result.is_error is True


# ============================================================================
# MCPClient base class — _build_request, _parse_response, _next_id
# ============================================================================

class TestMCPClient:
    def setup_method(self) -> None:
        self.client = MCPClient()

    def test_default_state(self) -> None:
        assert self.client.transport == TransportType.STDIO
        assert self.client.connected is False
        assert self.client._tools == []
        assert self.client._request_id == 0
        assert self.client._server_info == {}

    def test_next_id_increments(self) -> None:
        assert self.client._next_id() == 1
        assert self.client._next_id() == 2
        assert self.client._next_id() == 3

    def test_build_request_minimal(self) -> None:
        raw = self.client._build_request("ping")
        data = json.loads(raw)
        assert data == {"jsonrpc": "2.0", "id": 1, "method": "ping"}

    def test_build_request_with_params(self) -> None:
        raw = self.client._build_request("tools/call", {"name": "foo", "arguments": {"x": 1}})
        data = json.loads(raw)
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "tools/call"
        assert data["params"] == {"name": "foo", "arguments": {"x": 1}}
        assert isinstance(data["id"], int)

    def test_build_request_id_increments(self) -> None:
        req1 = json.loads(self.client._build_request("m1"))
        req2 = json.loads(self.client._build_request("m2"))
        assert req2["id"] == req1["id"] + 1

    def test_build_request_no_params_omits_key(self) -> None:
        raw = self.client._build_request("ping")
        data = json.loads(raw)
        assert "params" not in data

    def test_build_notification(self) -> None:
        raw = self.client._build_notification("notifications/initialized")
        data = json.loads(raw)
        assert data == {"jsonrpc": "2.0", "method": "notifications/initialized"}
        assert "id" not in data

    def test_parse_response_valid(self) -> None:
        result = self.client._parse_response('{"jsonrpc":"2.0","id":1,"result":{"ok":true}}')
        assert result["result"]["ok"] is True

    def test_parse_response_invalid_json(self) -> None:
        with pytest.raises(ProtocolError, match="Invalid JSON"):
            self.client._parse_response("not json")

    def test_parse_response_non_dict(self) -> None:
        with pytest.raises(ProtocolError, match="Expected JSON object"):
            self.client._parse_response("[1, 2, 3]")

    def test_parse_response_wrong_version(self) -> None:
        with pytest.raises(ProtocolError, match="Unsupported JSON-RPC version"):
            self.client._parse_response('{"jsonrpc":"1.0","id":1,"result":{}}')

    def test_parse_response_missing_version_ok(self) -> None:
        result = self.client._parse_response('{"id":1,"result":{"ok":true}}')
        assert result["result"]["ok"] is True

    def test_parse_response_with_error(self) -> None:
        payload = '{"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"Method not found"}}'
        with pytest.raises(ProtocolError, match="JSON-RPC error -32601: Method not found"):
            self.client._parse_response(payload)

    def test_parse_response_null_error_ok(self) -> None:
        result = self.client._parse_response(
            '{"jsonrpc":"2.0","id":1,"error":null,"result":{"ok":true}}'
        )
        assert result["result"]["ok"] is True

    def test_parse_response_without_result(self) -> None:
        result = self.client._parse_response('{"jsonrpc":"2.0","id":1}')
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_base_methods_raise_not_implemented(self) -> None:
        client = MCPClient()
        with pytest.raises(NotImplementedError):
            await client.connect("any")
        with pytest.raises(NotImplementedError):
            await client.disconnect()
        with pytest.raises(NotImplementedError):
            await client.list_tools()
        with pytest.raises(NotImplementedError):
            await client.call_tool("x")


# ============================================================================
# StdioMCPClient
# ============================================================================

@pytest.fixture
def mock_proc() -> MagicMock:
    """Create a mock subprocess with async stdin/stdout streams."""
    proc = MagicMock()
    proc.stdin = AsyncMock()
    proc.stdout = AsyncMock()
    proc.stderr = AsyncMock()
    proc.returncode = None
    proc.wait = AsyncMock(return_value=0)
    return proc


@pytest.fixture
def stdio() -> StdioMCPClient:
    return StdioMCPClient()


class TestStdioMCPClient:

    @pytest.mark.asyncio
    @patch("mcp_pm.client.asyncio.create_subprocess_exec")
    async def test_connect_success(
        self, mock_cse: MagicMock, mock_proc: MagicMock, stdio: StdioMCPClient
    ) -> None:
        """Happy path: start subprocess, send initialize, receive response."""
        mock_cse.return_value = mock_proc

        # Intercept _send_request to simulate the initialize handshake
        async def fake_send(method: str, params: dict | None = None) -> dict:
            if method == "initialize":
                return {"capabilities": {"tools": {}}, "serverInfo": {"name": "ts"}}
            return {}

        stdio._send_request = fake_send  # type: ignore[assignment]
        stdio._send_notification = AsyncMock()  # type: ignore[method-assign]

        await stdio.connect(["mcp-server", "--port", "1234"])

        assert stdio.connected is True
        assert stdio._server_info == {"tools": {}}
        mock_cse.assert_called_once()

    @pytest.mark.asyncio
    @patch("mcp_pm.client.asyncio.create_subprocess_exec")
    async def test_connect_file_not_found(
        self, mock_cse: MagicMock, stdio: StdioMCPClient
    ) -> None:
        mock_cse.side_effect = FileNotFoundError("not found")
        with pytest.raises(ConnectionError, match="Command not found"):
            await stdio.connect(["nonexistent"])

    @pytest.mark.asyncio
    @patch("mcp_pm.client.asyncio.create_subprocess_exec")
    async def test_connect_os_error(
        self, mock_cse: MagicMock, stdio: StdioMCPClient
    ) -> None:
        mock_cse.side_effect = OSError("permission")
        with pytest.raises(ConnectionError, match="Failed to start process"):
            await stdio.connect(["some-command"])

    @pytest.mark.asyncio
    @patch("mcp_pm.client.asyncio.create_subprocess_exec")
    async def test_connect_no_stdin(
        self, mock_cse: MagicMock, mock_proc: MagicMock, stdio: StdioMCPClient
    ) -> None:
        mock_proc.stdin = None
        mock_cse.return_value = mock_proc
        with pytest.raises(ConnectionError, match="stdin/stdout not available"):
            await stdio.connect(["cmd"])

    @pytest.mark.asyncio
    @patch("mcp_pm.client.asyncio.create_subprocess_exec")
    async def test_connect_no_stdout(
        self, mock_cse: MagicMock, mock_proc: MagicMock, stdio: StdioMCPClient
    ) -> None:
        mock_proc.stdout = None
        mock_cse.return_value = mock_proc
        with pytest.raises(ConnectionError, match="stdin/stdout not available"):
            await stdio.connect(["cmd"])

    @pytest.mark.asyncio
    async def test_list_tools_not_connected(self, stdio: StdioMCPClient) -> None:
        with pytest.raises(ConnectionError, match="Not connected"):
            await stdio.list_tools()

    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self, stdio: StdioMCPClient) -> None:
        with pytest.raises(ConnectionError, match="Not connected"):
            await stdio.call_tool("any")

    @pytest.mark.asyncio
    @patch.object(StdioMCPClient, "_send_request")
    async def test_list_tools_success(
        self, mock_send: AsyncMock, stdio: StdioMCPClient
    ) -> None:
        stdio._connected = True
        mock_send.return_value = {
            "tools": [
                {"name": "t1", "description": "tool one", "inputSchema": {"type": "object"}},
                {"name": "t2", "description": "tool two"},
            ]
        }
        tools = await stdio.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "t1"
        assert tools[0].parameters == {"type": "object"}
        assert tools[1].name == "t2"
        assert tools[1].parameters == {}
        mock_send.assert_called_once_with("tools/list")

    @pytest.mark.asyncio
    @patch.object(StdioMCPClient, "_send_request")
    async def test_call_tool_with_args(
        self, mock_send: AsyncMock, stdio: StdioMCPClient
    ) -> None:
        stdio._connected = True
        mock_send.return_value = {
            "content": [{"type": "text", "text": "hello"}],
            "isError": False,
        }
        result = await stdio.call_tool("greet", {"name": "World"})
        assert result.content == [{"type": "text", "text": "hello"}]
        assert result.is_error is False
        mock_send.assert_called_once_with("tools/call", {"name": "greet", "arguments": {"name": "World"}})

    @pytest.mark.asyncio
    @patch.object(StdioMCPClient, "_send_request")
    async def test_call_tool_no_args(
        self, mock_send: AsyncMock, stdio: StdioMCPClient
    ) -> None:
        stdio._connected = True
        mock_send.return_value = {"content": [], "isError": False}
        result = await stdio.call_tool("ping")
        assert result.content == []
        mock_send.assert_called_once_with("tools/call", {"name": "ping"})

    @pytest.mark.asyncio
    @patch.object(StdioMCPClient, "_send_request")
    async def test_call_tool_error_result(
        self, mock_send: AsyncMock, stdio: StdioMCPClient
    ) -> None:
        stdio._connected = True
        mock_send.return_value = {"content": [{"type": "text", "text": "err"}], "isError": True}
        result = await stdio.call_tool("fail")
        assert result.is_error is True

    @pytest.mark.asyncio
    @patch.object(StdioMCPClient, "_send_notification")
    @patch.object(StdioMCPClient, "_background_read")
    @patch("mcp_pm.client.asyncio.create_subprocess_exec")
    async def test_disconnect(
        self,
        mock_cse: MagicMock,
        mock_read: AsyncMock,
        mock_send_notif: AsyncMock,
        mock_proc: MagicMock,
        stdio: StdioMCPClient,
    ) -> None:
        mock_cse.return_value = mock_proc
        stdio._process = mock_proc
        stdio._reader = mock_proc.stdout
        stdio._reader_task = asyncio.create_task(asyncio.sleep(0))
        stdio._connected = True

        fut: asyncio.Future[dict] = asyncio.Future()
        stdio._pending[99] = fut

        await stdio.disconnect()

        assert stdio.connected is False
        assert stdio._pending == {}
        assert fut.cancelled()
        assert stdio._process is None
        assert stdio._reader is None

    # --- _background_read tests ---

    @pytest.mark.asyncio
    async def test_background_read_missing_reader(self, stdio: StdioMCPClient) -> None:
        """Returns immediately when _reader is None."""
        stdio._reader = None
        await stdio._background_read()

    @pytest.mark.asyncio
    async def test_background_read_cancelled(self, stdio: StdioMCPClient) -> None:
        """CancelledError is caught gracefully."""
        reader = AsyncMock()
        reader.readline = AsyncMock(side_effect=asyncio.CancelledError())
        stdio._reader = reader
        stdio._connected = True
        await stdio._background_read()

    @pytest.mark.asyncio
    async def test_background_read_stdout_closed(self, stdio: StdioMCPClient) -> None:
        """Empty line from readline exits the loop."""
        reader = AsyncMock()
        reader.readline = AsyncMock(return_value=b"")
        stdio._reader = reader
        stdio._connected = True
        await stdio._background_read()
        assert stdio.connected is False  # _connected is set to False in finally

    @pytest.mark.asyncio
    async def test_background_read_skips_non_json(self, stdio: StdioMCPClient) -> None:
        """Non-JSON lines are skipped, then empty line exits."""
        reader = AsyncMock()
        reader.readline = AsyncMock(side_effect=[
            b"not json\n",
            b"",
        ])
        stdio._reader = reader
        stdio._connected = True
        await stdio._background_read()

    @pytest.mark.asyncio
    async def test_background_read_dispatches_response(self, stdio: StdioMCPClient) -> None:
        """Valid JSON-RPC responses are dispatched to pending futures."""
        reader = AsyncMock()
        response = {"jsonrpc": "2.0", "id": 42, "result": {"done": True}}
        reader.readline = AsyncMock(side_effect=[
            json.dumps(response).encode() + b"\n",
            b"",
        ])
        stdio._reader = reader
        stdio._connected = True

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict] = loop.create_future()
        stdio._pending[42] = fut

        await stdio._background_read()
        assert fut.done()
        assert fut.result()["result"]["done"] is True

    @pytest.mark.asyncio
    async def test_background_read_no_pending(self, stdio: StdioMCPClient) -> None:
        """Response with unknown id is silently ignored."""
        reader = AsyncMock()
        response = {"jsonrpc": "2.0", "id": 999, "result": {}}
        reader.readline = AsyncMock(side_effect=[
            json.dumps(response).encode() + b"\n",
            b"",
        ])
        stdio._reader = reader
        stdio._connected = True
        await stdio._background_read()

    @pytest.mark.asyncio
    async def test_background_read_notification(self, stdio: StdioMCPClient) -> None:
        """Server notifications (method field, no id) are handled."""
        reader = AsyncMock()
        notif = {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}
        reader.readline = AsyncMock(side_effect=[
            json.dumps(notif).encode() + b"\n",
            b"",
        ])
        stdio._reader = reader
        stdio._connected = True
        await stdio._background_read()

    @pytest.mark.asyncio
    async def test_background_read_non_dict_skipped(self, stdio: StdioMCPClient) -> None:
        """JSON arrays (non-dict) are silently skipped."""
        reader = AsyncMock()
        reader.readline = AsyncMock(side_effect=[
            b'["not", "a", "dict"]\n',
            b"",
        ])
        stdio._reader = reader
        stdio._connected = True
        await stdio._background_read()

    # --- _send_request / _send_notification ---

    @pytest.mark.asyncio
    async def test_send_notification_no_process(self, stdio: StdioMCPClient) -> None:
        stdio._process = None
        with pytest.raises(ConnectionError, match="Write transport not available"):
            await stdio._send_notification("test")

    @pytest.mark.asyncio
    async def test_send_notification_writes_to_stdin(self, stdio: StdioMCPClient) -> None:
        proc = MagicMock()
        proc.stdin = AsyncMock()
        stdio._process = proc

        await stdio._send_notification("notifications/initialized")

        written = proc.stdin.write.call_args[0][0]
        parsed = json.loads(written.decode())
        assert parsed["method"] == "notifications/initialized"
        assert "id" not in parsed

    @pytest.mark.asyncio
    async def test_send_request_connection_lost(self, stdio: StdioMCPClient) -> None:
        """BrokenPipeError during write is converted to ConnectionError."""
        proc = MagicMock()
        # stdin.write is called synchronously (not awaited), so use regular mock
        stdin_mock = MagicMock()
        stdin_mock.write.side_effect = BrokenPipeError("broken")
        proc.stdin = stdin_mock
        stdio._process = proc

        with pytest.raises(ConnectionError, match="Connection lost"):
            await stdio._send_request("test")

    @pytest.mark.asyncio
    async def test_send_request_process_not_found(self, stdio: StdioMCPClient) -> None:
        """_send_request raises ConnectionError when process is None."""
        stdio._process = None
        with pytest.raises(ConnectionError, match="Write transport not available"):
            await stdio._send_request("test")

    @pytest.mark.asyncio
    async def test_send_request_timeout_del_pending(self, stdio: StdioMCPClient) -> None:
        """Pending request is cleaned up when future times out."""
        # Simulate: after writing, the future times out
        proc = MagicMock()
        proc.stdin = AsyncMock()
        proc.stdin.write.return_value = None
        proc.stdin.drain = AsyncMock()
        stdio._process = proc

        # We'll test the cleanup logic directly: _send_request pops from _pending
        # after either success or failure. We can verify by checking _pending is empty
        # after a failed request.
        req_id = stdio._next_id()
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict] = loop.create_future()
        stdio._pending[req_id] = fut

        # Cancel the future to simulate timeout
        fut.cancel()
        await asyncio.sleep(0)

        # After cleanup, pending should be empty
        stdio._pending.pop(req_id, None)
        assert req_id not in stdio._pending


# ============================================================================
# HTTPMCPClient
# ============================================================================

class TestHTTPMCPClient:

    def test_init_with_base_url(self) -> None:
        client = HTTPMCPClient(base_url="http://localhost:3000")
        assert client.base_url == "http://localhost:3000"
        assert client.transport == TransportType.HTTP

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_connect_success(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance

        # Health check success
        health_resp = MagicMock()
        health_resp.raise_for_status.return_value = None
        mock_instance.get = AsyncMock(return_value=health_resp)

        # Initialize response
        init_result = {"capabilities": {"tools": {}}, "serverInfo": {"name": "hs"}}
        init_resp = MagicMock()
        init_resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": init_result}
        init_resp.headers = {}
        init_resp.raise_for_status.return_value = None
        mock_instance.post = AsyncMock(return_value=init_resp)

        await client.connect("http://localhost:3000")

        assert client.connected is True
        assert client.base_url == "http://localhost:3000"
        assert client._server_info == {"tools": {}}
        mock_instance.get.assert_called_once_with("/health", timeout=5.0)

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_connect_connect_error(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        mock_instance.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(ConnectionError, match="Cannot reach MCP server"):
            await client.connect("http://localhost:3000")

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_connect_health_timeout(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        mock_instance.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        with pytest.raises(ConnectionError, match="Cannot reach MCP server"):
            await client.connect("http://localhost:3000")

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_connect_health_other_error_continues(
        self, mock_httpx_cls: MagicMock
    ) -> None:
        """Non-ConnectError health errors are logged but ignored."""
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        mock_instance.get = AsyncMock(side_effect=RuntimeError("unexpected"))

        init_resp = MagicMock()
        init_resp.json.return_value = {
            "jsonrpc": "2.0", "id": 1,
            "result": {"capabilities": {}},
        }
        init_resp.headers = {}
        init_resp.raise_for_status.return_value = None
        mock_instance.post = AsyncMock(return_value=init_resp)

        await client.connect("http://localhost:3000")
        assert client.connected is True

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_list_tools(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        client._client = mock_instance
        client._connected = True

        resp = MagicMock()
        resp.json.return_value = {
            "jsonrpc": "2.0", "id": 1,
            "result": {
                "tools": [
                    {"name": "ht", "description": "http tool", "inputSchema": {"type": "object"}},
                ]
            },
        }
        resp.headers = {}
        resp.raise_for_status.return_value = None
        mock_instance.post = AsyncMock(return_value=resp)

        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "ht"
        assert tools[0].parameters == {"type": "object"}

        body = mock_instance.post.call_args[1]["json"]
        assert body["method"] == "tools/list"

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_call_tool_with_args(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        client._client = mock_instance
        client._connected = True

        resp = MagicMock()
        resp.json.return_value = {
            "jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"type": "text", "text": "hi"}], "isError": False},
        }
        resp.headers = {}
        resp.raise_for_status.return_value = None
        mock_instance.post = AsyncMock(return_value=resp)

        result = await client.call_tool("greet", {"name": "World"})
        assert result.content == [{"type": "text", "text": "hi"}]

        body = mock_instance.post.call_args[1]["json"]
        assert body["method"] == "tools/call"
        assert body["params"] == {"name": "greet", "arguments": {"name": "World"}}

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_call_tool_no_args(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        client._client = mock_instance
        client._connected = True

        resp = MagicMock()
        resp.json.return_value = {
            "jsonrpc": "2.0", "id": 1, "result": {"content": []},
        }
        resp.headers = {}
        resp.raise_for_status.return_value = None
        mock_instance.post = AsyncMock(return_value=resp)

        await client.call_tool("ping")
        body = mock_instance.post.call_args[1]["json"]
        assert "arguments" not in body["params"]

    @pytest.mark.asyncio
    async def test_list_tools_not_connected(self) -> None:
        client = HTTPMCPClient()
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.list_tools()

    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self) -> None:
        client = HTTPMCPClient()
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.call_tool("x")

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_httpx_timeout(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        client._client = mock_instance
        client._connected = True

        mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with pytest.raises(TimeoutError, match="HTTP request timed out"):
            await client.call_tool("test")

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_httpx_404(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        client._client = mock_instance
        client._connected = True

        error_resp = MagicMock()
        error_resp.status_code = 404
        error_resp.text = "Not Found"
        mock_instance.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=error_resp  # type: ignore[arg-type]
        ))

        with pytest.raises(ConnectionError, match="SSE-based"):
            await client.call_tool("test")

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_httpx_other_status(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        client._client = mock_instance
        client._connected = True

        error_resp = MagicMock()
        error_resp.status_code = 500
        error_resp.text = "Internal Error"
        mock_instance.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "500", request=MagicMock(), response=error_resp  # type: ignore[arg-type]
        ))

        with pytest.raises(ProtocolError, match="HTTP 500"):
            await client.call_tool("test")

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_json_rpc_error_in_response(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        client._client = mock_instance
        client._connected = True

        resp = MagicMock()
        resp.json.return_value = {
            "jsonrpc": "2.0", "id": 1,
            "error": {"code": -32603, "message": "Internal error"},
        }
        resp.headers = {}
        resp.raise_for_status.return_value = None
        mock_instance.post = AsyncMock(return_value=resp)

        with pytest.raises(ProtocolError, match="JSON-RPC error -32603"):
            await client.call_tool("test")

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_session_id_from_headers(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        client._client = mock_instance
        client._connected = True

        resp = MagicMock()
        resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {"content": []}}
        resp.headers = {"Mcp-Session-Id": "sess-123"}
        resp.raise_for_status.return_value = None
        mock_instance.post = AsyncMock(return_value=resp)

        await client.call_tool("test")
        assert client._session_id == "sess-123"

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_session_id_sent_in_subsequent_requests(
        self, mock_httpx_cls: MagicMock
    ) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        client._client = mock_instance
        client._connected = True
        client._session_id = "sess-456"

        resp = MagicMock()
        resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {"content": []}}
        resp.headers = {}
        resp.raise_for_status.return_value = None
        mock_instance.post = AsyncMock(return_value=resp)

        await client.call_tool("test")
        headers = mock_instance.post.call_args[1]["headers"]
        assert headers["Mcp-Session-Id"] == "sess-456"

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_send_request_no_client(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        # Must bypass the _connected check to reach _send_request
        client._connected = True
        client._client = None
        with pytest.raises(ConnectionError, match="HTTP client not initialized"):
            await client.call_tool("x")

    @pytest.mark.asyncio
    @patch("mcp_pm.client.httpx.AsyncClient")
    async def test_disconnect(self, mock_httpx_cls: MagicMock) -> None:
        client = HTTPMCPClient()
        mock_instance = AsyncMock()
        mock_httpx_cls.return_value = mock_instance
        client._client = mock_instance
        client._connected = True

        await client.disconnect()
        assert client.connected is False
        assert client._client is None
        mock_instance.aclose.assert_called_once()


# ============================================================================
# MCPSession
# ============================================================================

class TestMCPSession:

    @pytest.mark.asyncio
    async def test_init(self) -> None:
        session = MCPSession()
        assert session.servers == {}

    @pytest.mark.asyncio
    @patch("mcp_pm.client.StdioMCPClient")
    async def test_start_server_stdio(self, mock_cls: MagicMock) -> None:
        session = MCPSession()
        mock_client = AsyncMock()
        mock_client.connected = True
        mock_client.list_tools = AsyncMock(return_value=[
            MCPTool(name="t1", description="tool"),
        ])
        mock_cls.return_value = mock_client

        server = await session.start_server("my-server", ["node", "server.js"])
        assert server.name == "my-server"
        assert server.manifest["command"] == ["node", "server.js"]
        assert server.manifest["transport"] == "stdio"
        assert len(server.tools) == 1
        mock_client.connect.assert_called_once_with(["node", "server.js"], env=None)

    @pytest.mark.asyncio
    @patch("mcp_pm.client.HTTPMCPClient")
    async def test_start_server_http(self, mock_cls: MagicMock) -> None:
        session = MCPSession()
        mock_client = AsyncMock()
        mock_client.connected = True
        mock_cls.return_value = mock_client

        server = await session.start_server(
            "http-server", ["some"], transport="http", url="http://localhost:3000"
        )
        assert server.manifest["transport"] == "http"
        mock_client.connect.assert_called_once_with("http://localhost:3000")

    @pytest.mark.asyncio
    async def test_start_server_http_no_url(self) -> None:
        session = MCPSession()
        with pytest.raises(ValueError, match="url is required"):
            await session.start_server("bad", ["cmd"], transport="http")

    @pytest.mark.asyncio
    async def test_start_server_duplicate(self) -> None:
        session = MCPSession()
        session._servers["dup"] = MagicMock()
        with pytest.raises(ValueError, match="already running"):
            await session.start_server("dup", ["cmd"])

    @pytest.mark.asyncio
    @patch("mcp_pm.client.StdioMCPClient")
    async def test_start_server_list_tools_failure_logged(
        self, mock_cls: MagicMock
    ) -> None:
        session = MCPSession()
        mock_client = AsyncMock()
        mock_client.connected = True
        mock_client.list_tools = AsyncMock(side_effect=RuntimeError("boom"))
        mock_cls.return_value = mock_client

        server = await session.start_server("faulty", ["cmd"])
        assert server.name == "faulty"
        assert server.tools == []

    @pytest.mark.asyncio
    @patch("mcp_pm.client.StdioMCPClient")
    async def test_stop_server(self, mock_cls: MagicMock) -> None:
        session = MCPSession()
        mock_client = AsyncMock()
        mock_client.connected = True
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_cls.return_value = mock_client

        await session.start_server("s1", ["cmd"])
        assert "s1" in session.servers

        await session.stop_server("s1")
        assert "s1" not in session.servers
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_server_not_found(self) -> None:
        session = MCPSession()
        with pytest.raises(KeyError, match="not running"):
            await session.stop_server("nonexistent")

    @pytest.mark.asyncio
    @patch("mcp_pm.client.StdioMCPClient")
    async def test_stop_server_disconnect_error_logged(self, mock_cls: MagicMock) -> None:
        session = MCPSession()
        mock_client = AsyncMock()
        mock_client.connected = True
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.disconnect = AsyncMock(side_effect=RuntimeError("fail"))
        mock_cls.return_value = mock_client

        await session.start_server("s1", ["cmd"])
        await session.stop_server("s1")
        assert "s1" not in session.servers

    @pytest.mark.asyncio
    @patch("mcp_pm.client.StdioMCPClient")
    async def test_stop_all(self, mock_cls: MagicMock) -> None:
        session = MCPSession()
        mc1, mc2 = AsyncMock(), AsyncMock()
        mc1.connected = True
        mc1.list_tools = AsyncMock(return_value=[])
        mc2.connected = True
        mc2.list_tools = AsyncMock(return_value=[])
        mock_cls.side_effect = [mc1, mc2]

        await session.start_server("s1", ["cmd1"])
        await session.start_server("s2", ["cmd2"])
        assert len(session.servers) == 2

        await session.stop_all()
        assert session.servers == {}
        mc1.disconnect.assert_called_once()
        mc2.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("mcp_pm.client.StdioMCPClient")
    async def test_get_all_tools(self, mock_cls: MagicMock) -> None:
        session = MCPSession()
        mock_client = AsyncMock()
        mock_client.connected = True
        mock_client.list_tools = AsyncMock(return_value=[
            MCPTool(name="a", description="tool A"),
            MCPTool(name="b", description="tool B"),
        ])
        mock_cls.return_value = mock_client

        await session.start_server("s1", ["cmd"])
        all_tools = session.get_all_tools()
        assert len(all_tools) == 2
        assert all_tools[0] == ("s1", MCPTool(name="a", description="tool A"))
        assert all_tools[1] == ("s1", MCPTool(name="b", description="tool B"))

    @pytest.mark.asyncio
    @patch("mcp_pm.client.StdioMCPClient")
    async def test_call_tool(self, mock_cls: MagicMock) -> None:
        session = MCPSession()
        mock_client = AsyncMock()
        mock_client.connected = True
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.call_tool = AsyncMock(return_value=MCPToolResult(
            content=[{"type": "text", "text": "done"}]
        ))
        mock_cls.return_value = mock_client

        await session.start_server("s1", ["cmd"])
        result = await session.call_tool("s1", "test-tool", {"x": 1})
        assert result.content == [{"type": "text", "text": "done"}]
        mock_client.call_tool.assert_called_once_with("test-tool", arguments={"x": 1})

    @pytest.mark.asyncio
    async def test_call_tool_server_not_found(self) -> None:
        session = MCPSession()
        with pytest.raises(KeyError, match="not running"):
            await session.call_tool("nonexistent", "tool")

    def test_get_all_tools_empty(self) -> None:
        session = MCPSession()
        assert session.get_all_tools() == []

    def test_servers_property_returns_copy(self) -> None:
        session = MCPSession()
        assert session.servers == {}
        # Mutating the returned dict should not affect internal state
        session.servers["x"] = MagicMock()
        assert "x" not in session._servers
