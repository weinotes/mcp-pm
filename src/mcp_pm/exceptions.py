# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""
Custom exceptions for mcp-pm.

Provides a typed exception hierarchy for all error conditions.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""


class McpPmError(Exception):
    """Base exception for all mcp-pm errors."""


class RegistryError(McpPmError):
    """Error communicating with a registry backend."""


class InstallError(McpPmError):
    """Error during server installation/uninstallation."""


class ClientError(McpPmError):
    """Error communicating with an MCP server."""


class ConfigError(McpPmError):
    """Error in configuration."""


class SandboxError(McpPmError):
    """Error in sandbox operations."""
