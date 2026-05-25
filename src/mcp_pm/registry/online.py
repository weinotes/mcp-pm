# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""Online registry backends — MCP.so, GitHub, Smithery, npm, PyPI."""
from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from mcp_pm.registry.base import RegistryBackend
from mcp_pm.registry.models import ServerManifest

logger = logging.getLogger(__name__)

USER_AGENT = "mcp-pm/0.1.0"


class McpSoBackend(RegistryBackend):
    """Query MCP.so's search API.

    API endpoints (reverse-engineered from mcp.so):
      - Search: GET https://mcp.so/api/search?q={query}
      - Detail: GET https://mcp.so/api/servers/{name}
      - Popular: GET https://mcp.so/api/servers/popular
    """

    name = "mcpso"
    base_url = "https://mcp.so"  # Note: API may be unavailable — falls back gracefully

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                timeout=httpx.Timeout(4.0),
            )
        return self._client

    def _parse_server(self, raw: dict[str, Any]) -> ServerManifest | None:
        """Parse a raw MCP.so API response entry into ServerManifest."""
        try:
            name = raw.get("name") or raw.get("slug") or ""
            if not name:
                return None

            source_type = "git"
            source_url = raw.get("sourceUrl") or raw.get("github") or ""
            if source_url:
                if source_url.startswith("http"):
                    source_type = "git"
                elif source_url.startswith("npm"):
                    source_type = "npm"
            else:
                pkg = raw.get("package", "")
                if pkg and pkg.startswith("npm"):
                    source_type = "npm"
                    source_url = pkg
                elif pkg and pkg.startswith("pip"):
                    source_type = "pip"
                    source_url = pkg

            tags: list[str] = []
            raw_tags = raw.get("tags") or raw.get("categories") or []
            if isinstance(raw_tags, list):
                tags = [str(t) for t in raw_tags if t]

            stars = raw.get("stars", 0)
            if isinstance(stars, str):
                try:
                    stars = int(stars)
                except (ValueError, TypeError):
                    stars = 0

            return ServerManifest(
                name=name,
                description=raw.get("description", "") or "",
                source_type=source_type,
                source_url=source_url,
                author=raw.get("author"),
                homepage=raw.get("homepage") or raw.get("website"),
                license=raw.get("license"),
                stars=stars,
                tags=tags,
                tools_count=int(raw.get("toolsCount", raw.get("tools_count", 0)) or 0),
            )
        except Exception as exc:
            logger.debug("Failed to parse MCP.so server entry: %s", exc)
            return None

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search MCP.so by query string."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/search",
                params={"q": query, "limit": min(limit, 50)},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("MCP.so search failed: %s", exc)
            return []

        entries: list[dict[str, Any]] = []
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("data", data.get("results", data.get("servers", [])))

        results: list[ServerManifest] = []
        for entry in entries[:limit]:
            parsed = self._parse_server(entry)
            if parsed:
                results.append(parsed)
        return results

    async def get(self, name: str) -> ServerManifest | None:
        """Get a single server detail from MCP.so."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/servers/{name}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("MCP.so get '%s' failed: %s", name, exc)
            return None

        entry = data.get("data", data) if isinstance(data, dict) else data
        return self._parse_server(entry)

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        """Get popular MCP servers from MCP.so."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/servers/popular",
                params={"limit": min(limit, 50)},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("MCP.so popular failed: %s", exc)
            return []

        entries: list[dict[str, Any]] = []
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("data", data.get("results", data.get("servers", [])))

        results: list[ServerManifest] = []
        for entry in entries[:limit]:
            parsed = self._parse_server(entry)
            if parsed:
                results.append(parsed)
        return results


class GitHubRegistryBackend(RegistryBackend):
    """Query GitHub MCP Registry API."""

    name = "github_registry"
    base_url = "https://registry.mcpservers.ai/api"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=httpx.Timeout(4.0),
            )
        return self._client

    def _parse_server(self, raw: dict[str, Any]) -> ServerManifest | None:
        try:
            name = raw.get("name") or raw.get("id") or ""
            if not name:
                return None

            repo_url = (
                raw.get("repository")
                or raw.get("repo")
                or raw.get("sourceUrl")
                or raw.get("githubUrl")
                or ""
            )
            pkg = raw.get("package") or raw.get("install") or ""

            source_type = "git"
            source_url = repo_url

            if pkg:
                if pkg.startswith("npm") or "npm" in pkg:
                    source_type = "npm"
                    source_url = pkg
                elif pkg.startswith("pip") or pkg.startswith("uvx"):
                    source_type = "pip"
                    source_url = pkg

            tags: list[str] = []
            raw_tags = raw.get("tags") or raw.get("categories") or []
            if isinstance(raw_tags, list):
                tags = [str(t) for t in raw_tags if t]

            stars = raw.get("stars", 0)
            if isinstance(stars, str):
                try:
                    stars = int(stars)
                except (ValueError, TypeError):
                    stars = 0

            return ServerManifest(
                name=name,
                description=raw.get("description", "") or "",
                source_type=source_type,
                source_url=source_url,
                author=raw.get("author") or raw.get("owner"),
                homepage=raw.get("homepage") or raw.get("website"),
                license=raw.get("license"),
                stars=stars,
                tags=tags,
                tools_count=int(raw.get("tools_count", raw.get("toolsCount", 0)) or 0),
            )
        except Exception as exc:
            logger.debug("Failed to parse GitHub Registry entry: %s", exc)
            return None

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/servers",
                params={"search": query, "limit": min(limit, 50)},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("GitHub Registry search failed: %s", exc)
            return []

        entries: list[dict[str, Any]] = []
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("data", data.get("results", data.get("servers", [])))

        results: list[ServerManifest] = []
        for entry in entries[:limit]:
            parsed = self._parse_server(entry)
            if parsed:
                results.append(parsed)
        return results

    async def get(self, name: str) -> ServerManifest | None:
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/servers/{name}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("GitHub Registry get '%s' failed: %s", name, exc)
            return None

        entry = data.get("data", data) if isinstance(data, dict) else data
        return self._parse_server(entry)


class SmitheryBackend(RegistryBackend):
    """Query Smithery API."""

    name = "smithery"
    base_url = "https://registry.smithery.ai"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=httpx.Timeout(4.0),
            )
        return self._client

    def _parse_server(self, raw: dict[str, Any]) -> ServerManifest | None:
        try:
            name = raw.get("name") or raw.get("qualifiedName") or raw.get("id") or ""
            if not name:
                return None

            connections = raw.get("connections") or {}
            deployment = raw.get("deployment") or raw.get("install") or {}

            source_type = "git"
            source_url = raw.get("repository") or raw.get("github") or ""

            pkg_cmd = deployment.get("command", "") if isinstance(deployment, dict) else ""
            if pkg_cmd:
                if "npx" in pkg_cmd or "npm" in pkg_cmd:
                    source_type = "npm"
                    source_url = pkg_cmd
                elif "pip" in pkg_cmd or "uvx" in pkg_cmd:
                    source_type = "pip"
                    source_url = pkg_cmd
                elif "docker" in pkg_cmd:
                    source_type = "docker"
                    source_url = pkg_cmd

            if not source_url and isinstance(connections, dict):
                source_url = connections.get("github", "")

            tags: list[str] = []
            raw_tags = raw.get("tags") or raw.get("categories") or []
            if isinstance(raw_tags, list):
                tags = [str(t) for t in raw_tags if t]

            stars = raw.get("stars", 0)
            if isinstance(stars, str):
                try:
                    stars = int(stars)
                except (ValueError, TypeError):
                    stars = 0
            if not stars:
                uc = raw.get("useCount", 0)
                if isinstance(uc, (int, float)) and uc > 0:
                    stars = uc

            return ServerManifest(
                name=name,
                description=raw.get("description", "") or "",
                source_type=source_type,
                source_url=source_url,
                author=raw.get("author") or raw.get("publisher"),
                homepage=raw.get("homepage") or raw.get("url"),
                license=raw.get("license"),
                stars=stars,
                tags=tags,
                tools_count=int(raw.get("toolsCount", raw.get("tools_count", 0)) or 0),
            )
        except Exception as exc:
            logger.debug("Failed to parse Smithery entry: %s", exc)
            return None

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/servers",
                params={"search": query, "limit": min(limit, 50)},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Smithery search failed: %s", exc)
            return []

        entries: list[dict[str, Any]] = []
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("data", data.get("results", data.get("servers", [])))

        results: list[ServerManifest] = []
        for entry in entries[:limit]:
            parsed = self._parse_server(entry)
            if parsed:
                results.append(parsed)
        return results

    async def get(self, name: str) -> ServerManifest | None:
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/servers/{name}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("Smithery get '%s' failed: %s", name, exc)
            return None

        entry = data.get("data", data) if isinstance(data, dict) else data
        return self._parse_server(entry)

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/servers",
                params={"sort": "stars", "order": "desc", "limit": min(limit, 50)},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Smithery popular failed: %s", exc)
            return []

        entries: list[dict[str, Any]] = []
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("data", data.get("results", data.get("servers", [])))

        results: list[ServerManifest] = []
        for entry in entries[:limit]:
            parsed = self._parse_server(entry)
            if parsed:
                results.append(parsed)
        return results


class NpmRegistryBackend(RegistryBackend):
    """Search npm registry for MCP server packages."""

    name = "npm"
    base_url = "https://registry.npmjs.org"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=httpx.Timeout(4.0),
            )
        return self._client

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        client = await self._get_client()
        results: list[ServerManifest] = []
        try:
            resp = await client.get(
                f"{self.base_url}/-/v1/search",
                params={"text": f"mcp-server {query}", "size": min(limit, 50)},
            )
            resp.raise_for_status()
            data = resp.json()
            for obj in data.get("objects", [])[:limit]:
                pkg = obj.get("package", {})
                name = pkg.get("name", "")
                if not name or "mcp" not in name.lower():
                    continue
                results.append(ServerManifest(
                    name=name,
                    description=pkg.get("description", ""),
                    source_type="npm",
                    source_url=name,
                    author=pkg.get("publisher", {}).get("username", "npm"),
                    homepage=pkg.get("links", {}).get("npm", ""),
                    stars=obj.get("score", {}).get("detail", {}).get("quality", 0),
                ))
        except Exception as exc:
            logger.debug("npm search failed: %s", exc)
        return results

    async def get(self, name: str) -> ServerManifest | None:
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/{name.replace('/', '%2F')}")
            resp.raise_for_status()
            data = resp.json()
            return ServerManifest(
                name=data.get("name", name),
                description=data.get("description", ""),
                source_type="npm",
                source_url=data.get("name", name),
                author=(
                    data.get("author", {}).get("name", "npm")
                    if isinstance(data.get("author"), dict)
                    else str(data.get("author", "npm"))
                ),
                homepage=data.get("homepage", ""),
                license=data.get("license", ""),
            )
        except Exception as exc:
            logger.debug("npm get '%s' failed: %s", name, exc)
            return None

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        return await self.search("", limit)


class McpRegistryBackend(RegistryBackend):
    """Query the official MCP Registry API (registry.modelcontextprotocol.io).

    The official MCP Registry is the community-driven primary source of
    truth for MCP servers, maintained by the MCP Steering Committee.
    No API key is required.

    API: GET https://registry.modelcontextprotocol.io/v0/servers
    Params: search, limit, cursor
    Docs: https://registry.modelcontextprotocol.io/docs
    """

    name = "mcp_registry"
    base_url = "https://registry.modelcontextprotocol.io"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=httpx.Timeout(4.0),
            )
        return self._client

    def _parse_server(self, raw: dict[str, Any]) -> ServerManifest | None:
        try:
            name = raw.get("name") or raw.get("id") or raw.get("qualifiedName") or ""
            if not name:
                return None

            source_type = "git"
            source_url = raw.get("repository") or raw.get("source_url", "")
            install_cmd = raw.get("command", raw.get("install", ""))
            if isinstance(install_cmd, str):
                if "npx" in install_cmd or "npm" in install_cmd:
                    source_type = "npm"
                    source_url = source_url or install_cmd
                elif "pip" in install_cmd or "uvx" in install_cmd:
                    source_type = "pip"
                    source_url = source_url or install_cmd
                elif "docker" in install_cmd:
                    source_type = "docker"
                    source_url = source_url or install_cmd
            elif isinstance(install_cmd, dict):
                pkg = str(install_cmd.get("package", ""))
                if "npx" in pkg or "npm" in pkg:
                    source_type = "npm"
                elif "pip" in pkg or "uvx" in pkg:
                    source_type = "pip"

            tags: list[str] = []
            raw_tags = raw.get("tags") or raw.get("categories", [])
            if isinstance(raw_tags, list):
                tags = [str(t) for t in raw_tags if t]
            elif isinstance(raw_tags, str) and raw_tags:
                tags = [raw_tags]

            return ServerManifest(
                name=name,
                description=raw.get("description", "") or "",
                source_type=source_type,
                source_url=source_url or "",
                author=raw.get("author") or raw.get("publisher"),
                homepage=raw.get("homepage") or raw.get("url", raw.get("website")),
                license=raw.get("license"),
                stars=int(raw.get("stars", raw.get("useCount", 0)) or 0),
                tags=tags,
                tools_count=int(raw.get("tools_count", raw.get("toolsCount", 0)) or 0),
            )
        except Exception as exc:
            logger.debug("Failed to parse MCP Registry entry: %s", exc)
            return None

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/v0/servers",
                params={"search": query, "limit": min(limit, 50)},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("MCP Registry search failed: %s", exc)
            return []

        entries: list[dict[str, Any]] = []
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("data", data.get("servers", data.get("results", [])))

        results: list[ServerManifest] = []
        for entry in entries[:limit]:
            parsed = self._parse_server(entry)
            if parsed:
                results.append(parsed)
        return results

    async def get(self, name: str) -> ServerManifest | None:
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/v0/servers",
                params={"search": name, "limit": 10},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("MCP Registry get '%s' failed: %s", name, exc)
            return None

        entries: list[dict[str, Any]] = []
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("data", data.get("servers", data.get("results", [])))

        for entry in entries:
            parsed = self._parse_server(entry)
            if parsed and parsed.name == name:
                return parsed
        return None

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        return await self.search("", limit)


class PyPIRegistryBackend(RegistryBackend):
    """Search PyPI for MCP server packages."""

    name = "pypi"
    base_url = "https://pypi.org"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=httpx.Timeout(4.0),
            )
        return self._client

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        client = await self._get_client()
        results: list[ServerManifest] = []
        try:
            resp = await client.get(
                f"{self.base_url}/search/",
                params={"q": f"mcp {query}"},
                headers={"Accept": "text/html"},
            )
            resp.raise_for_status()
            pkg_names: set[str] = set()
            for m in re.finditer(r'/project/([^/\"]+)/', resp.text):
                name = m.group(1)
                if "mcp" in name.lower() and name not in pkg_names:
                    pkg_names.add(name)
                    if len(pkg_names) >= limit:
                        break

            for pkg_name in list(pkg_names)[:limit]:
                try:
                    detail = await client.get(
                        f"{self.base_url}/pypi/{pkg_name}/json",
                        timeout=httpx.Timeout(3.0),
                    )
                    if detail.status_code == 200:
                        info = detail.json().get("info", {})
                        results.append(ServerManifest(
                            name=info.get("name", pkg_name),
                            description=info.get("summary", ""),
                            source_type="pip",
                            source_url=info.get("name", pkg_name),
                            author=info.get("author", "PyPI"),
                            homepage=info.get("home_page", ""),
                            license=info.get("license", ""),
                        ))
                except Exception as exc:
                    logger.debug("Failed to parse PyPI result: %s", exc)
                    continue
        except Exception as exc:
            logger.debug("PyPI search failed: %s", exc)
        return results

    async def get(self, name: str) -> ServerManifest | None:
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/pypi/{name}/json")
            resp.raise_for_status()
            data = resp.json()
            info = data.get("info", {})
            return ServerManifest(
                name=info.get("name", name),
                description=info.get("summary", ""),
                source_type="pip",
                source_url=info.get("name", name),
                author=info.get("author", "PyPI"),
                homepage=info.get("home_page", ""),
                license=info.get("license", ""),
            )
        except Exception as exc:
            logger.debug("PyPI get '%s' failed: %s", name, exc)
            return None

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        return await self.search("mcp-server", limit)
