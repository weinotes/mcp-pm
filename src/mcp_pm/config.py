"""
Configuration management for mcp-pm.

Handles reading, writing, importing, and exporting configuration.
Uses YAML format for human readability and editability.

Config path: ~/.mcp-pm/config.yaml
Servers path: ~/.mcp-pm/servers/

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".mcp-pm" / "config.yaml"


class Config:
    """Manages mcp-pm configuration."""

    def __init__(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        self.path = path
        self._data: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        """Load configuration from disk."""
        if self.path.exists():
            raw = self.path.read_text(encoding="utf-8")
            self._data = yaml.safe_load(raw) or {}
        return self._data

    def save(self) -> None:
        """Save configuration to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(yaml.dump(self._data, default_flow_style=False), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dot-separated key (e.g. 'registry.url')."""
        parts = key.split(".")
        data = self._data
        for part in parts:
            if isinstance(data, dict):
                data = data.get(part)
            else:
                return default
        return data if data is not None else default

    def set(self, key: str, value: Any) -> None:
        """Set a config value by dot-separated key."""
        parts = key.split(".")
        data = self._data
        for part in parts[:-1]:
            if part not in data or not isinstance(data[part], dict):
                data[part] = {}
            data = data[part]
        data[parts[-1]] = value

    def export(self) -> str:
        """Export config as YAML string."""
        return yaml.dump(self._data, default_flow_style=False)

    def import_str(self, yaml_str: str) -> None:
        """Import config from YAML string."""
        self._data = yaml.safe_load(yaml_str) or {}
