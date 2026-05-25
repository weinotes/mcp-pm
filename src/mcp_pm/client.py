# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""MCP client — connects to MCP servers via stdio or HTTP transport.

Handles JSON-RPC message exchange, tool discovery, and tool invocation
according to the Model Context Protocol specification.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
DEFAULT_TIMEOUT = 30.0


class TransportType(StrEnum):
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class ProtocolError(Exception):
    """Raised on JSON-RPC protocol violations."""


@dataclass
class MCPTool:
    """Represents a tool exposed by an MCP server."""

    name: str
    description: str
    parameters: dict[str, object] = field(default_factory=dict)


@dataclass
class MCPToolResult:
    """Result from invoking an MCP tool."""

    content: list[dict[str, Any]]
    is_error: bool = False


class MCPClient:
    """Client for communicating with MCP servers using JSON-RPC 2.0."""

    def __init__(self, transport: TransportType = TransportType.STDIO) -> None:
        self.transport = transport
        self._tools: list[MCPTool] = []
        self._request_id = 0
        self._connected = False
        self._server_info: dict[str, Any] = {}

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self, endpoint: str) -> None:
        """Connect to an MCP server at the given endpoint."""
        raise NotImplementedError

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        raise NotImplementedError

    async def list_tools(self) -> list[MCPTool]:
        """Discover available tools from the server."""
        raise NotImplementedError

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> MCPToolResult:
        """Invoke a tool on the server."""
        raise NotImplementedError

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _build_request(self, method: str, params: dict[str, Any] | None = None) -> str:
        """Build a JSON-RPC 2.0 request string."""
        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            request["params"] = params
        return json.dumps(request)

    def _build_notification(self, method: str, params: dict[str, Any] | None = None) -> str:
        """Build a JSON-RPC 2.0 notification string (no id)."""
        notification: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            notification["params"] = params
        return json.dumps(notification)

    @staticmethod
    def _parse_response(raw: str) -> dict[str, Any]:
        """Parse a JSON-RPC 2.0 response, raising on errors."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProtocolError(f"Invalid JSON response: {exc}") from exc

        if not isinstance(data, dict):
            raise ProtocolError(f"Expected JSON object, got {type(data).__name__}")

        if "jsonrpc" in data and data["jsonrpc"] != "2.0":
            raise ProtocolError(f"Unsupported JSON-RPC version: {data['jsonrpc']}")

        if "error" in data and data["error"] is not None:
            err = data["error"]
            code = err.get("code", -1)
            message = err.get("message", "Unknown error")
            raise ProtocolError(f"JSON-RPC error {code}: {message}")

        return data


class StdioMCPClient(MCPClient):
    """MCP client that communicates with a subprocess via stdio."""

    def __init__(self) -> None:
        super().__init__(transport=TransportType.STDIO)
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None

    async def connect(self, command: list[str], env: dict[str, str] | None = None) -> None:
        """Start the subprocess and establish the JSON-RPC connection.

        Args:
            command: The command and arguments to start the MCP server process.
            env: Optional environment variables to merge with the current environment.

        Raises:
            ConnectionError: If the subprocess fails to start or initialize.
        """
        merged_env = {**os.environ, **(env or {})}

        try:
            self._process = await asyncio.create_subprocess_exec(
                *command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged_env,
            )
        except FileNotFoundError as exc:
            raise ConnectionError(f"Command not found: {' '.join(command)}") from exc
        except OSError as exc:
            raise ConnectionError(f"Failed to start process: {exc}") from exc

        if self._process.stdin is None or self._process.stdout is None:
            raise ConnectionError("Subprocess stdin/stdout not available")

        # Use the process streams directly
        self._reader = self._process.stdout

        # Start background reader
        self._reader_task = asyncio.create_task(self._background_read())

        # Send initialize request
        init_response = await self._send_request("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": "mcp-pm",
                "version": "0.1.0",
            },
        })

        self._server_info = init_response.get("capabilities", {})
        logger.info(
            "MCP server initialized: %s",
            init_response.get("serverInfo", {}).get("name", "unknown"),
        )

        # Send initialized notification
        await self._send_notification("notifications/initialized")

        self._connected = True

    async def disconnect(self) -> None:
        """Send a close signal and terminate the subprocess."""
        self._connected = False

        # Cancel pending requests
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

        # Cancel background reader
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

        # Send exit notification
        with contextlib.suppress(Exception):
            await self._send_notification("exit")

        # Terminate the process
        if self._process is not None and self._process.returncode is None:
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except TimeoutError:
                    self._process.kill()
                    await self._process.wait()
            except ProcessLookupError:
                pass

        self._process = None
        self._reader = None

    async def list_tools(self) -> list[MCPTool]:
        """Send a tools/list request and return the discovered tools."""
        if not self._connected:
            raise ConnectionError("Not connected to MCP server")

        result = await self._send_request("tools/list")
        raw_tools = result.get("tools", [])
        tools: list[MCPTool] = []
        for raw in raw_tools:
            tools.append(MCPTool(
                name=raw.get("name", ""),
                description=raw.get("description", ""),
                parameters=raw.get("inputSchema", raw.get("parameters", {})),
            ))
        self._tools = tools
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> MCPToolResult:
        """Send a tools/call request and return the result.

        Args:
            name: The name of the tool to invoke.
            arguments: Optional arguments to pass to the tool.

        Returns:
            MCPToolResult containing the tool's response content.

        Raises:
            ConnectionError: If not connected.
            ProtocolError: If the server returns an error.
        """
        if not self._connected:
            raise ConnectionError("Not connected to MCP server")

        params: dict[str, Any] = {"name": name}
        if arguments is not None:
            params["arguments"] = arguments

        result = await self._send_request("tools/call", params)
        return MCPToolResult(
            content=result.get("content", []),
            is_error=result.get("isError", False),
        )

    async def _send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the response."""
        request_id = self._next_id()
        future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        raw = json.dumps(request) + "\n"
        logger.debug("Sending request: %s", raw.strip())

        try:
            if self._process is None or self._process.stdin is None:
                raise ConnectionError("Write transport not available")
            self._process.stdin.write(raw.encode("utf-8"))
            await self._process.stdin.drain()

            try:
                response = await asyncio.wait_for(future, timeout=DEFAULT_TIMEOUT)
            except TimeoutError:
                del self._pending[request_id]
                raise TimeoutError(f"Request timed out after {DEFAULT_TIMEOUT}s: {method}") from None

            if "error" in response and response["error"] is not None:
                err = response["error"]
                raise ProtocolError(
                    f"JSON-RPC error {err.get('code', -1)}: {err.get('message', 'Unknown')}"
                )

            return response.get("result", {})
        except (BrokenPipeError, ConnectionResetError) as exc:
            raise ConnectionError(f"Connection lost: {exc}") from exc
        finally:
            self._pending.pop(request_id, None)

    async def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        notification: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            notification["params"] = params

        raw = json.dumps(notification) + "\n"
        logger.debug("Sending notification: %s", raw.strip())

        if self._process is None or self._process.stdin is None:
            raise ConnectionError("Write transport not available")
        self._process.stdin.write(raw.encode("utf-8"))
        await self._process.stdin.drain()

    async def _background_read(self) -> None:
        """Continuously read lines from stdout and dispatch responses."""
        if self._reader is None:
            return

        try:
            while self._connected:
                try:
                    raw_line = await asyncio.wait_for(
                        self._reader.readline(), timeout=0.5
                    )
                except TimeoutError:
                    continue

                if not raw_line:
                    logger.debug("MCP server stdout closed")
                    break

                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue

                logger.debug("Received line: %s", line)

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Non-JSON output from MCP server: %s", line[:200])
                    continue

                if not isinstance(data, dict):
                    continue

                # Handle responses (has 'id')
                if "id" in data and data["id"] is not None:
                    req_id = data["id"]
                    future = self._pending.get(req_id)
                    if future is not None and not future.done():
                        future.set_result(data)
                    else:
                        logger.debug("No pending request for id %s", req_id)

                # Handle notifications and server-sent events
                elif "method" in data:
                    logger.debug("Received notification: %s", data.get("method"))

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Background reader error: %s", exc)
        finally:
            self._connected = False


class HTTPMCPClient(MCPClient):
    """MCP client that communicates via HTTP POST /message."""

    def __init__(self, base_url: str = "") -> None:
        super().__init__(transport=TransportType.HTTP)
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None
        self._session_id: str | None = None

    async def connect(self, endpoint: str) -> None:
        """Connect to an MCP server via HTTP.

        Args:
            endpoint: The base URL of the MCP HTTP server (e.g. http://localhost:3000).

        Raises:
            ConnectionError: If the server is unreachable.
        """
        self.base_url = endpoint.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(DEFAULT_TIMEOUT),
        )

        # Check connectivity
        try:
            resp = await self._client.get("/health", timeout=5.0)
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ConnectionError(f"Cannot reach MCP server at {self.base_url}: {exc}") from exc
        except Exception as exc:
            logger.debug("Health endpoint not available for %s: %s", self.base_url, exc)
            pass

        # Send initialize request via POST /message
        result = await self._send_request("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": "mcp-pm",
                "version": "0.1.0",
            },
        })

        self._server_info = result.get("capabilities", {})
        logger.info(
            "MCP HTTP server initialized: %s",
            result.get("serverInfo", {}).get("name", "unknown"),
        )

        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the HTTP MCP server."""
        self._connected = False
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def list_tools(self) -> list[MCPTool]:
        """Send a tools/list request via HTTP."""
        if not self._connected:
            raise ConnectionError("Not connected to MCP server")

        result = await self._send_request("tools/list")
        raw_tools = result.get("tools", [])
        tools: list[MCPTool] = []
        for raw in raw_tools:
            tools.append(MCPTool(
                name=raw.get("name", ""),
                description=raw.get("description", ""),
                parameters=raw.get("inputSchema", raw.get("parameters", {})),
            ))
        self._tools = tools
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> MCPToolResult:
        """Send a tools/call request via HTTP."""
        if not self._connected:
            raise ConnectionError("Not connected to MCP server")

        params: dict[str, Any] = {"name": name}
        if arguments is not None:
            params["arguments"] = arguments

        result = await self._send_request("tools/call", params)
        return MCPToolResult(
            content=result.get("content", []),
            is_error=result.get("isError", False),
        )

    async def _send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC request via HTTP POST /message."""
        if self._client is None:
            raise ConnectionError("HTTP client not initialized")

        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            request["params"] = params

        logger.debug("HTTP request: %s %s", method, params)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        try:
            resp = await self._client.post("/message", json=request, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"HTTP request timed out: {method}") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Try the stream endpoint for servers that use SSE transport
                raise ConnectionError(
                    f"MCP endpoint not found at {self.base_url}/message. "
                    "Is this an SSE-based server?"
                ) from exc
            raise ProtocolError(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
        except Exception as exc:
            raise ProtocolError(f"HTTP request failed: {exc}") from exc

        # Extract session ID from response headers
        if "Mcp-Session-Id" in resp.headers:
            self._session_id = resp.headers["Mcp-Session-Id"]

        if isinstance(data, dict) and "error" in data and data["error"] is not None:
            err = data["error"]
            raise ProtocolError(
                f"JSON-RPC error {err.get('code', -1)}: {err.get('message', 'Unknown')}"
            )

        return data.get("result", data) if isinstance(data, dict) else data


@dataclass
class MCPServer:
    """Runtime MCP server instance, containing the client and metadata."""

    name: str
    manifest: dict[str, Any]
    client: MCPClient
    tools: list[MCPTool] = field(default_factory=list)


class MCPSession:
    """Manages a collection of connected MCP server instances.

    Provides a unified interface for discovering tools across all servers
    and routing tool calls to the appropriate server.
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCPServer] = {}

    @property
    def servers(self) -> dict[str, MCPServer]:
        """Get all registered servers keyed by name."""
        return dict(self._servers)

    async def start_server(
        self,
        name: str,
        command: list[str],
        env: dict[str, str] | None = None,
        transport: str = "stdio",
        url: str | None = None,
    ) -> MCPServer:
        """Start and connect an MCP server.

        Args:
            name: A unique name for this server instance.
            command: The command and arguments to start the server process
                     (used with stdio transport).
            env: Optional environment variables.
            transport: Transport type: "stdio" or "http".
            url: Base URL for HTTP transport (required if transport="http").

        Returns:
            The MCPServer instance.

        Raises:
            ValueError: If a server with the same name already exists.
            ConnectionError: If the server fails to connect.
        """
        if name in self._servers:
            raise ValueError(f"Server '{name}' is already running")

        if transport == "http":
            if not url:
                raise ValueError("url is required for HTTP transport")
            client = HTTPMCPClient()
            await client.connect(url)
        else:
            client = StdioMCPClient()
            await client.connect(command, env=env)

        manifest: dict[str, Any] = {
            "command": command,
            "env": env,
            "transport": transport,
        }

        server = MCPServer(name=name, manifest=manifest, client=client)
        self._servers[name] = server

        # Discover tools
        try:
            server.tools = await client.list_tools()
        except Exception as exc:
            logger.warning("Failed to list tools for '%s': %s", name, exc)

        return server

    async def stop_server(self, name: str) -> None:
        """Disconnect and remove a server.

        Args:
            name: The name of the server to stop.

        Raises:
            KeyError: If the server is not found.
        """
        if name not in self._servers:
            raise KeyError(f"Server '{name}' is not running")

        server = self._servers.pop(name)
        try:
            await server.client.disconnect()
        except Exception as exc:
            logger.warning("Error disconnecting '%s': %s", name, exc)

    async def stop_all(self) -> None:
        """Disconnect and remove all servers."""
        names = list(self._servers.keys())
        for name in names:
            await self.stop_server(name)

    def get_all_tools(self) -> list[tuple[str, MCPTool]]:
        """Get all tools from all servers.

        Returns:
            A list of (server_name, MCPTool) tuples.
        """
        result: list[tuple[str, MCPTool]] = []
        for server_name, server in self._servers.items():
            for tool in server.tools:
                result.append((server_name, tool))
        return result

    async def call_tool(
        self, server_name: str, tool_name: str, args: dict[str, Any] | None = None
    ) -> MCPToolResult:
        """Call a tool on a specific server.

        Args:
            server_name: The name of the server hosting the tool.
            tool_name: The name of the tool to invoke.
            args: Optional arguments to pass to the tool.

        Returns:
            MCPToolResult containing the tool's response.

        Raises:
            KeyError: If the server is not found.
        """
        if server_name not in self._servers:
            raise KeyError(f"Server '{server_name}' is not running")

        server = self._servers[server_name]
        return await server.client.call_tool(tool_name, arguments=args)
