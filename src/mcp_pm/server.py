# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""HTTP proxy server — exposes all installed MCP tools via OpenAI-compatible API.

Provides:
- POST /v1/chat/completions — OpenAI-compatible chat completions with tool calling
  (supports both non-streaming and SSE streaming responses)
- POST /v1/tools — list available tools in OpenAI tool format
- GET /health — health check

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from mcp_pm.client import MCPSession, MCPTool, MCPToolResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI schema helpers
# ---------------------------------------------------------------------------


def mcp_tool_to_openai(tool: MCPTool) -> dict[str, Any]:
    """Convert an MCPTool to an OpenAI-compatible tool definition.

    The OpenAI tools API expects:
    {
        "type": "function",
        "function": {
            "name": "...",
            "description": "...",
            "parameters": {...}   # JSON Schema object
        }
    }
    """
    params = dict(tool.parameters)

    # Ensure inputSchema has the required JSON Schema fields
    if "$schema" not in params and "type" not in params:
        params = {
            "type": "object",
            "properties": params,
            "required": [],
        }
    elif "type" not in params:
        params = {
            "type": "object",
            "properties": {},
            "required": [],
            **params,
        }

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": params,
        },
    }


async def _handle_tool_calls(
    session: MCPSession,
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Execute tool calls and return results in OpenAI format.

    Each tool_call in the request looks like:
    {
        "id": "call_xxx",
        "type": "function",
        "function": {"name": "...", "arguments": "{...}"}
    }

    Returns a list of tool result messages:
    {
        "role": "tool",
        "tool_call_id": "call_xxx",
        "content": "..."
    }
    """
    results: list[dict[str, Any]] = []

    # Build mapping: server_name -> list of (tool_name, tool_call_id, args)
    # We need to find which server hosts each tool
    server_tool_map: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    for tc in tool_calls:
        func = tc.get("function", {})
        tool_name = func.get("name", "")
        tool_call_id = tc.get("id", "")
        try:
            args = json.loads(func.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            args = {}

        # Find which server has this tool
        found = False
        for srv_name, srv in session.servers.items():
            for tool_def in srv.tools:
                if tool_def.name == tool_name:
                    server_tool_map.setdefault(srv_name, []).append(
                        (tool_name, tool_call_id, args)
                    )
                    found = True
                    break
            if found:
                break

        if not found:
            results.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps({"error": f"Tool '{tool_name}' not found on any server"}),
            })

    # Execute tool calls per server concurrently
    async def _call_server_tools(
        srv_name: str, calls: list[tuple[str, str, dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        srv_results: list[dict[str, Any]] = []
        for tool_name, tool_call_id, args in calls:
            try:
                mcp_result: MCPToolResult = await session.call_tool(
                    srv_name, tool_name, args
                )
                # Convert MCPToolResult content to string
                content_parts: list[str] = []
                for item in mcp_result.content:
                    if isinstance(item, dict):
                        text = item.get("text", json.dumps(item, ensure_ascii=False))
                        content_parts.append(text)
                    else:
                        content_parts.append(str(item))
                content = "\n".join(content_parts)

                result_entry: dict[str, Any] = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": content,
                }
                if mcp_result.is_error:
                    result_entry["is_error"] = True
                srv_results.append(result_entry)
            except Exception as exc:
                srv_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": str(exc)}),
                    "is_error": True,
                })
        return srv_results

    if server_tool_map:
        tasks = [
            _call_server_tools(srv, calls)
            for srv, calls in server_tool_map.items()
        ]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        for batch in batch_results:
            if isinstance(batch, list):
                results.extend(batch)
            elif isinstance(batch, Exception):
                logger.error("Tool call batch failed: %s", batch)

    return results


# ---------------------------------------------------------------------------
# FastAPI application factory
# ---------------------------------------------------------------------------


def create_app(session: MCPSession) -> FastAPI:
    """Create a FastAPI application bound to the given MCPSession.

    The application provides OpenAI-compatible endpoints that route
    through the session's connected MCP servers.
    """
    app = FastAPI(
        title="mcp-pm Proxy Server",
        version="0.1.0",
        description="OpenAI-compatible API proxy for MCP tools",
    )

    # Store session in app state for access in routes
    app.state.session = session

    # -----------------------------------------------------------------------
    # Health check
    # -----------------------------------------------------------------------

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Health check endpoint."""
        tool_count = sum(len(s.tools) for s in session.servers.values())
        return {
            "status": "ok",
            "version": "0.1.0",
            "servers_loaded": len(session.servers),
            "tools_loaded": tool_count,
            "servers": list(session.servers.keys()),
        }

    # -----------------------------------------------------------------------
    # List tools (OpenAI format)
    # -----------------------------------------------------------------------

    @app.post("/v1/tools")
    @app.get("/v1/tools")
    async def list_tools() -> dict[str, Any]:
        """List all available tools from all connected MCP servers.

        Returns tools in OpenAI-compatible format:
        {"object":"list","data":[{"type":"function","function":{...}}]}
        """
        all_tools: list[dict[str, Any]] = []
        for srv_name, srv in session.servers.items():
            for tool in srv.tools:
                openai_tool = mcp_tool_to_openai(tool)
                # Tag with server name for disambiguation
                openai_tool["function"]["_server"] = srv_name
                all_tools.append(openai_tool)

        return {"object": "list", "data": all_tools}

    # -----------------------------------------------------------------------
    # Chat completions (OpenAI-compatible)
    # -----------------------------------------------------------------------

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Any:
        """OpenAI-compatible chat completions endpoint.

        Accepts:
        {
            "model": "...",           # optional, ignored
            "messages": [...],        # list of chat messages
            "tools": [...],           # optional tool definitions
            "tool_choice": "auto",    # optional
            "stream": false           # optional, SSE streaming
        }

        When tool calls are present in the response, the endpoint will
        automatically execute the tools and return the results.
        """
        body: dict[str, Any] = await request.json()
        messages: list[dict[str, Any]] = body.get("messages", [])
        stream: bool = body.get("stream", False)

        # Collect all available tools from the session
        available_tools: list[dict[str, Any]] = []
        for srv_name, srv in session.servers.items():
            for tool in srv.tools:
                ot = mcp_tool_to_openai(tool)
                ot["function"]["_server"] = srv_name
                available_tools.append(ot)

        # Generate a completion response with tool declarations
        # Since mcp-pm is a proxy, we simulate a model that knows about
        # all the available tools. The model name is echoed back.
        model = body.get("model", "mcp-proxy")

        # Extract the last user message for a basic response
        user_msg = next(
            (m for m in reversed(messages) if m.get("role") == "user"),
            {"content": ""},
        )
        user_content = user_msg.get("content", "")

        # Handle tool_choice
        tool_choice = body.get("tool_choice", "auto")

        if stream:
            return StreamingResponse(
                _stream_chat_completions(
                    user_content=user_content,
                    available_tools=available_tools,
                    messages=messages,
                    model=model,
                    session=session,
                    tool_choice=tool_choice,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        # Non-streaming response
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(asyncio.get_event_loop().time())

        response = await _build_non_streaming_response(
            user_content=user_content,
            available_tools=available_tools,
            messages=messages,
            model=model,
            session=session,
            tool_choice=tool_choice,
            response_id=response_id,
            created=created,
        )
        return response

    return app


# ---------------------------------------------------------------------------
# Non-streaming response builder
# ---------------------------------------------------------------------------


async def _build_non_streaming_response(
    user_content: str,
    available_tools: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    model: str,
    session: MCPSession,
    tool_choice: str,
    response_id: str,
    created: int,
) -> dict[str, Any]:
    """Build a non-streaming chat completion response.

    If tools are available, we echo back tool_calls so the caller can
    execute them. If no tools, return a simple assistant message.
    """
    # Check if the last message has tool_calls that need to be processed
    last_msg = messages[-1] if messages else {}
    if last_msg.get("role") == "assistant" and "tool_calls" in last_msg:
        # Process tool calls
        tool_results = await _handle_tool_calls(session, last_msg["tool_calls"])
        response_message: dict[str, Any] = {
            "role": "assistant",
            "content": None,
        }
        choices = [
            {
                "index": 0,
                "message": response_message,
                "finish_reason": "stop",
                "logprobs": None,
            }
        ]
        return {
            "id": response_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": choices,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "tool_results": tool_results,
        }

    # Normal response — present available tools
    if available_tools and tool_choice != "none":
        # Create a tool_calls array that invites the client to pick a tool
        # We'll create a simple text response listing available tools
        tool_list_str = "\n".join(
            f"- {t['function']['name']}: {t['function']['description']}"
            for t in available_tools[:20]
        )
        if len(available_tools) > 20:
            tool_list_str += f"\n... and {len(available_tools) - 20} more"

        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": (
                f"I have {len(available_tools)} tools available from "
                f"{len(session.servers)} connected MCP servers. "
                f"Here are the available tools:\n\n{tool_list_str}\n\n"
                "You can call any of these tools using the tools API. "
                "Describe what you'd like to do and I'll help you use the right tool."
            ),
        }
    else:
        assistant_message = {
            "role": "assistant",
            "content": f"Received your message. Tools available: {len(available_tools)}.",
        }

    return {
        "id": response_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": assistant_message,
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


# ---------------------------------------------------------------------------
# SSE streaming response
# ---------------------------------------------------------------------------


async def _stream_chat_completions(
    user_content: str,
    available_tools: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    model: str,
    session: MCPSession,
    tool_choice: str,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for a streaming chat completion response.

    Yields OpenAI-compatible SSE events:
    - data: [DONE]
    - data: {"choices": [...], ...}
    """
    response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(asyncio.get_event_loop().time())

    # Check if the last message has tool_calls
    last_msg = messages[-1] if messages else {}
    if last_msg.get("role") == "assistant" and "tool_calls" in last_msg:
        # Process tool calls
        tool_results = await _handle_tool_calls(session, last_msg["tool_calls"])

        # Send the final result
        response_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": f"Executed {len(tool_results)} tool(s) successfully.",
                    },
                    "finish_reason": "stop",
                    "logprobs": None,
                }
            ],
            "tool_results": tool_results,
        }
        yield f"data: {json.dumps(response_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n"
        return

    # Streaming the tool list response
    intro_text = (
        f"I have {len(available_tools)} tools available from "
        f"{len(session.servers)} connected MCP servers.\n\n"
    )

    # Send intro
    intro_chunk = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": intro_text},
                "logprobs": None,
            }
        ],
    }
    yield "data: " + json.dumps(intro_chunk, ensure_ascii=False) + "\n\n"

    # List tools in chunks
    if available_tools:
        tool_lines = []
        for t in available_tools[:20]:
            name = t["function"]["name"]
            desc = t["function"]["description"]
            tool_lines.append(f"- **{name}**: {desc}")

        if len(available_tools) > 20:
            extra = len(available_tools) - 20
            tool_lines.append(f"\n... and {extra} more")

        chunk_text = "\n".join(tool_lines) + "\n\nDescribe what you'd like to do!"
        list_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk_text},
                    "logprobs": None,
                }
            ],
        }
        yield "data: " + json.dumps(list_chunk, ensure_ascii=False) + "\n\n"

    # Send finish
    finish_chunk = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
    }
    yield "data: " + json.dumps(finish_chunk, ensure_ascii=False) + "\n\n"

    yield "data: [DONE]\n"


# ---------------------------------------------------------------------------
# Server launcher
# ---------------------------------------------------------------------------


def start(
    session: MCPSession,
    host: str = "127.0.0.1",
    port: int = 8000,
    log_level: str = "info",
) -> None:
    """Start the proxy server using uvicorn.

    Args:
        session: An MCPSession with already-connected MCP servers.
        host: Bind address (default: 127.0.0.1).
        port: Bind port (default: 8000).
        log_level: Uvicorn log level (default: "info").
    """
    import uvicorn

    app = create_app(session)
    logger.info(
        "Starting mcp-pm proxy server on %s:%s with %d server(s)",
        host,
        port,
        len(session.servers),
    )
    uvicorn.run(app, host=host, port=port, log_level=log_level)
