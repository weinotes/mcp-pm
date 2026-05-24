# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""Tap backend — searches servers from installed third-party taps."""
from __future__ import annotations

from typing import Any

from mcp_pm.registry.base import RegistryBackend
from mcp_pm.registry.models import ServerManifest


class TapRegistryBackend(RegistryBackend):
    """Searches servers from installed third-party taps."""

    name = "tap"

    def __init__(self) -> None:
        from mcp_pm.tap import TapManager

        self._tm = TapManager()

    def _entry_to_manifest(self, entry: dict[str, Any]) -> ServerManifest:
        return ServerManifest(
            name=str(entry.get("name", "")),
            description=str(entry.get("description", entry.get("desc", ""))),
            source_type=str(entry.get("source_type", entry.get("type", "git"))),
            source_url=str(entry.get("source_url", entry.get("url", ""))),
            author=str(entry.get("author", entry.get("_tap", "tap"))),
        )

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        q = query.lower()
        results: list[ServerManifest] = []
        for entry in self._tm.load_tap_servers():
            name = str(entry.get("name", "")).lower()
            desc = str(entry.get("description", entry.get("desc", ""))).lower()
            if q in name or q in desc:
                results.append(self._entry_to_manifest(entry))
                if len(results) >= limit:
                    break
        return results

    async def get(self, name: str) -> ServerManifest | None:
        for entry in self._tm.load_tap_servers():
            if entry.get("name") == name:
                return self._entry_to_manifest(entry)
        return None

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        results: list[ServerManifest] = []
        for entry in self._tm.load_tap_servers()[:limit]:
            results.append(self._entry_to_manifest(entry))
        return results
