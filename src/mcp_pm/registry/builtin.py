# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""BuiltIn backend — curated index from YAML catalog."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from mcp_pm.registry.base import RegistryBackend
from mcp_pm.registry.models import ServerManifest

logger = logging.getLogger(__name__)


class BuiltInBackend(RegistryBackend):
    """Curated index of well-known MCP servers — always available, no network needed.

    Loads server catalog from ``data/catalog.yaml`` (bundled with the package).
    Merges additional servers from ``~/.mcp-pm/custom_servers.yaml`` if present,
    and from any path set in config ``registry.catalog_path``.
    """

    name = "builtin"
    _CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.yaml"
    _CUSTOM_PATH = Path.home() / ".mcp-pm" / "custom_servers.yaml"

    def __init__(self, extra_paths: list[Path] | None = None) -> None:
        self._extra_paths = extra_paths or []
        self._servers: list[dict[str, Any]] | None = None

    def _load_all(self) -> list[dict[str, Any]]:
        """Load and merge all server entries from catalog + custom sources."""
        if self._servers is not None:
            return self._servers

        entries: list[dict[str, Any]] = []

        # 1. Load bundled catalog
        if self._CATALOG_PATH.exists():
            try:
                raw = yaml.safe_load(self._CATALOG_PATH.read_text(encoding="utf-8"))
                for group in (raw or {}).get("catalog", []):
                    entries.extend(group.get("servers", []))
            except Exception as exc:
                logger.warning("Failed to load catalog: %s", exc)

        # 2. Load custom servers from ~/.mcp-pm/custom_servers.yaml
        if self._CUSTOM_PATH.exists():
            try:
                raw = yaml.safe_load(self._CUSTOM_PATH.read_text(encoding="utf-8"))
                for group in (raw or {}).get("catalog", []):
                    entries.extend(group.get("servers", []))
            except Exception as exc:
                logger.warning("Failed to load custom servers: %s", exc)

        # 3. Load extra paths (e.g. from config registry.catalog_path)
        for path in self._extra_paths:
            if path.exists():
                try:
                    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                    for group in (raw or {}).get("catalog", []):
                        entries.extend(group.get("servers", []))
                except Exception as exc:
                    logger.warning("Failed to load extra catalog %s: %s", path, exc)

        self._servers = entries
        return entries

    @property
    def _all_servers(self) -> list[dict[str, Any]]:
        """Get all servers, normalizing YAML keys to the internal format."""
        def _normalize(s: dict[str, Any]) -> dict[str, Any]:
            return {
                "name": s.get("name", ""),
                "desc": s.get("description", s.get("desc", "")),
                "type": s.get("source_type", s.get("type", "git")),
                "url": s.get("source_url", s.get("url", "")),
                "author": s.get("author", "Community"),
                "tools": s.get("tools_count", s.get("tools", 0)),
            }
        return [_normalize(s) for s in self._load_all()]

    @staticmethod
    def _is_relevant(text: str, query_words: set[str]) -> bool:
        """Check if any query word appears as a whole word in text."""
        text_lower = text.lower()
        for word in query_words:
            if re.search(rf"(^|[\W_]+){re.escape(word)}([\W_]+|$)", text_lower):
                return True
        return False

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search built-in index by name/description using whole-word matching."""
        query_words = {w.lower() for w in query.split() if w.strip()}
        if not query_words:
            return []

        results = []
        for s in self._all_servers:
            if not self._is_relevant(s["name"], query_words) \
               and not self._is_relevant(s["desc"], query_words) \
               and not self._is_relevant(s["author"], query_words):
                continue
            results.append(ServerManifest(
                name=s["name"],
                description=s["desc"],
                source_type=s["type"],
                source_url=s["url"],
                author=s["author"],
                tools_count=s["tools"],
            ))
            if len(results) >= limit:
                break
        return results

    async def get(self, name: str) -> ServerManifest | None:
        """Get a server by name from the built-in index."""
        for s in self._all_servers:
            if s["name"] == name:
                return ServerManifest(
                    name=s["name"],
                    description=s["desc"],
                    source_type=s["type"],
                    source_url=s["url"],
                    author=s["author"],
                    tools_count=s["tools"],
                )
        return None

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        """Return all built-in servers as 'popular' list."""
        results = []
        for s in self._all_servers[:limit]:
            results.append(ServerManifest(
                name=s["name"],
                description=s["desc"],
                source_type=s["type"],
                source_url=s["url"],
                author=s["author"],
                tools_count=s["tools"],
            ))
        return results
