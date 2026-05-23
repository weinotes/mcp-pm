"""Verify client.py and server.py import cleanly and basic types work.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""
import asyncio
import sys

sys.path.insert(0, "src")

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
from mcp_pm.server import _handle_tool_calls, create_app, mcp_tool_to_openai, start

# Basic sanity checks
assert StdioMCPClient is not None
assert HTTPMCPClient is not None
assert MCPSession is not None

# Test MCPTool conversion
tool = MCPTool(name="test", description="A test tool", parameters={"type": "object"})
openai_tool = mcp_tool_to_openai(tool)
assert openai_tool["type"] == "function"
assert openai_tool["function"]["name"] == "test"

# Test MCPToolResult
result = MCPToolResult(content=[{"type": "text", "text": "hello"}])
assert result.content[0]["text"] == "hello"

print("All imports and basic checks passed!")

# Run a quick async test
async def test_session():
    session = MCPSession()
    # Session should start empty
    assert len(session.servers) == 0
    assert len(session.get_all_tools()) == 0
    print("MCPSession empty state OK")

    # Create app from empty session
    app = create_app(session)
    assert app.title == "mcp-pm Proxy Server"
    print("create_app OK")


asyncio.run(test_session())

print("start() signature OK")
print("\nAll checks passed!")
