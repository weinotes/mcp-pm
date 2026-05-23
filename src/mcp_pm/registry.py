# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""
Registry client — discovers MCP servers from multiple backends.

Supports: MCP.so API, GitHub MCP Registry, Smithery API, and
a built-in curated index as fallback.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "mcp-pm/0.1.0"


@dataclass
class ServerManifest:
    """Metadata for an MCP server in the registry."""

    name: str
    description: str
    source_type: str  # git, npm, pip, docker
    source_url: str
    author: str | None = None
    homepage: str | None = None
    license: str | None = None
    stars: int = 0
    tags: list[str] = field(default_factory=list)
    tools_count: int = 0


class RegistryBackend(ABC):
    """Abstract base for registry backend implementations."""

    name: str = "base"

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search servers matching query."""
        ...

    @abstractmethod
    async def get(self, name: str) -> ServerManifest | None:
        """Get a single server by name."""
        ...

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        """Return popular/hot servers. Defaults to empty list."""
        return []


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
                timeout=httpx.Timeout(15.0),
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
                # Fallback: use package field
                pkg = raw.get("package", "")
                if pkg and pkg.startswith("npm"):
                    source_type = "npm"
                    source_url = pkg
                elif pkg and pkg.startswith("pip"):
                    source_type = "pip"
                    source_url = pkg

            # Try to extract tags
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

        # Response may be a list or a dict with 'data' key
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

        if isinstance(data, dict):
            entry = data.get("data", data)
        else:
            entry = data
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
    """Query GitHub MCP Registry API.

    The community MCP registry at https://registry.mcpservers.ai
    and also https://github.com/modelcontextprotocol/servers.

    Endpoints (community registry):
      - Search: GET https://registry.mcpservers.ai/api/servers?search={query}
      - Detail: GET https://registry.mcpservers.ai/api/servers/{name}
    """

    name = "github_registry"
    base_url = "https://registry.mcpservers.ai/api"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=httpx.Timeout(15.0),
            )
        return self._client

    def _parse_server(self, raw: dict[str, Any]) -> ServerManifest | None:
        """Parse a raw GitHub Registry API entry."""
        try:
            name = raw.get("name") or raw.get("id") or ""
            if not name:
                return None

            # Determine source type and URL
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
        """Search GitHub MCP Registry."""
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
        """Get a single server from GitHub Registry."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/servers/{name}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("GitHub Registry get '%s' failed: %s", name, exc)
            return None

        if isinstance(data, dict):
            entry = data.get("data", data)
        else:
            entry = data
        return self._parse_server(entry)


class SmitheryBackend(RegistryBackend):
    """Query Smithery API.

    Smithery is an MCP server registry at https://smithery.ai.

    Endpoints:
      - Search: GET https://registry.smithery.ai/api/servers?search={query}
      - Detail: GET https://registry.smithery.ai/api/servers/{name}
      - Popular: GET https://registry.smithery.ai/api/servers?sort=stars
    """

    name = "smithery"
    base_url = "https://registry.smithery.ai"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=httpx.Timeout(15.0),
            )
        return self._client

    def _parse_server(self, raw: dict[str, Any]) -> ServerManifest | None:
        """Parse a raw Smithery API entry."""
        try:
            name = raw.get("name") or raw.get("qualifiedName") or raw.get("id") or ""
            if not name:
                return None

            # Determine source type
            connections = raw.get("connections") or {}
            deployment = raw.get("deployment") or raw.get("install") or {}

            source_type = "git"
            source_url = raw.get("repository") or raw.get("github") or ""

            # Check if there's a package/deploy command hint
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

            # If source_url is still empty, try connections
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
        """Search Smithery registry."""
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
        """Get a single server from Smithery."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/servers/{name}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("Smithery get '%s' failed: %s", name, exc)
            return None

        if isinstance(data, dict):
            entry = data.get("data", data)
        else:
            entry = data
        return self._parse_server(entry)

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        """Get popular servers from Smithery (sorted by stars)."""
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


class BuiltInBackend(RegistryBackend):
    """Curated index of well-known MCP servers — always available, no network needed."""

    name = "builtin"

    # Curated list of popular MCP servers
    _SERVERS: list[dict[str, Any]] = [
        {"name": "filesystem", "desc": "Read, write, and manage files and directories", "type": "npm", "url": "@anthropic/mcp-server-filesystem", "author": "Anthropic", "tools": 12},
        {"name": "github", "desc": "Manage GitHub repos, issues, PRs, and workflows", "type": "npm", "url": "@anthropic/mcp-server-github", "author": "Anthropic", "tools": 15},
        {"name": "brave-search", "desc": "Web search using Brave Search API", "type": "npm", "url": "@anthropic/mcp-server-brave-search", "author": "Anthropic", "tools": 2},
        {"name": "fetch", "desc": "Fetch and convert web content to markdown", "type": "npm", "url": "@anthropic/mcp-server-fetch", "author": "Anthropic", "tools": 1},
        {"name": "puppeteer", "desc": "Browser automation with headless Chrome", "type": "npm", "url": "@anthropic/mcp-server-puppeteer", "author": "Anthropic", "tools": 8},
        {"name": "sqlite", "desc": "SQLite database exploration and querying", "type": "npm", "url": "@anthropic/mcp-server-sqlite", "author": "Anthropic", "tools": 3},
        {"name": "sentry", "desc": "Analyze Sentry issues and performance data", "type": "npm", "url": "mcp-server-sentry", "author": "Sentry", "tools": 6},
        {"name": "slack", "desc": "Slack messaging and channel management", "type": "npm", "url": "mcp-server-slack", "author": "Anthropic", "tools": 10},
        {"name": "postgres", "desc": "PostgreSQL database schema and query tool", "type": "npm", "url": "@anthropic/mcp-server-postgres", "author": "Anthropic", "tools": 5},
        {"name": "redis", "desc": "Redis key-value store operations", "type": "npm", "url": "mcp-server-redis", "author": "Anthropic", "tools": 4},
        {"name": "cloudflare", "desc": "Manage Cloudflare Workers, KV, R2, D1", "type": "npm", "url": "mcp-server-cloudflare", "author": "Cloudflare", "tools": 20},
        {"name": "exa", "desc": "Fast AI-powered web search and crawling", "type": "npm", "url": "mcp-server-exa", "author": "Exa", "tools": 3},
        {"name": "linear", "desc": "Linear issue tracking and project management", "type": "npm", "url": "mcp-server-linear", "author": "Linear", "tools": 8},
        {"name": "notion", "desc": "Notion pages, databases, and search", "type": "npm", "url": "mcp-server-notion", "author": "Anthropic", "tools": 10},
        {"name": "jira", "desc": "Jira issue management and project tracking", "type": "npm", "url": "mcp-server-jira", "author": "Anthropic", "tools": 8},
        {"name": "confluence", "desc": "Confluence wiki and documentation access", "type": "npm", "url": "mcp-server-confluence", "author": "Anthropic", "tools": 6},
        {"name": "gmail", "desc": "Read and send Gmail messages", "type": "pip", "url": "mcp-server-gmail", "author": "Smithery", "tools": 5},
        {"name": "google-sheets", "desc": "Google Sheets read/write/format", "type": "pip", "url": "mcp-server-google-sheets", "author": "Smithery", "tools": 7},
        {"name": "google-drive", "desc": "Google Drive file management", "type": "pip", "url": "mcp-server-google-drive", "author": "Smithery", "tools": 6},
        {"name": "youtube", "desc": "YouTube transcript and metadata retrieval", "type": "pip", "url": "mcp-server-youtube", "author": "Community", "tools": 3},
        {"name": "playwright", "desc": "Web scraping and browser automation", "type": "pip", "url": "mcp-server-playwright", "author": "Community", "tools": 8},
        {"name": "spotify", "desc": "Spotify music control and playlist management", "type": "pip", "url": "mcp-server-spotify", "author": "Community", "tools": 6},
        {"name": "discord", "desc": "Discord messaging and server management", "type": "pip", "url": "mcp-server-discord", "author": "Community", "tools": 5},
        {"name": "docker", "desc": "Docker container management", "type": "pip", "url": "mcp-server-docker", "author": "Community", "tools": 10},
        {"name": "kubernetes", "desc": "Kubernetes cluster management and operations", "type": "pip", "url": "mcp-server-kubernetes", "author": "Community", "tools": 12},
        {"name": "weather", "desc": "Weather forecast and current conditions", "type": "pip", "url": "mcp-server-weather", "author": "Community", "tools": 2},
        {"name": "mcp-pm", "desc": "Manage MCP servers with mcp-pm itself (meta!)", "type": "pip", "url": "mcp-pm", "author": "Davey Wong", "tools": 12},
    ]

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search built-in index by name/description."""
        q = query.lower()
        results = []
        for s in self._SERVERS:
            if q in s["name"].lower() or q in s["desc"].lower() or q in s["author"].lower():
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
        for s in self._SERVERS:
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
        for s in self._SERVERS[:limit]:
            results.append(ServerManifest(
                name=s["name"],
                description=s["desc"],
                source_type=s["type"],
                source_url=s["url"],
                author=s["author"],
                tools_count=s["tools"],
            ))
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
                timeout=httpx.Timeout(10.0),
            )
        return self._client

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search npm for MCP-related packages."""
        client = await self._get_client()
        results: list[ServerManifest] = []
        try:
            # Search npm for MCP packages matching the query
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
        """Get a single package from npm."""
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
                author=data.get("author", {}).get("name", "npm") if isinstance(data.get("author"), dict) else str(data.get("author", "npm")),
                homepage=data.get("homepage", ""),
                license=data.get("license", ""),
            )
        except Exception as exc:
            logger.debug("npm get '%s' failed: %s", name, exc)
            return None

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        """Get popular MCP packages from npm."""
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
                timeout=httpx.Timeout(10.0),
            )
        return self._client

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search PyPI for MCP-related packages."""
        client = await self._get_client()
        results: list[ServerManifest] = []
        try:
            resp = await client.get(
                f"{self.base_url}/search/",
                params={"q": f"mcp {query}", "page": 1},
            )
            resp.raise_for_status()
            data = resp.json()
            # PyPI search returns results in data.results
            for item in data.get("results", [])[:limit]:
                name = item.get("name", "")
                if not name or "mcp" not in name.lower():
                    continue
                results.append(ServerManifest(
                    name=name,
                    description=item.get("summary", ""),
                    source_type="pip",
                    source_url=name,
                    author=item.get("author", "PyPI"),
                    homepage=item.get("home_page", ""),
                    license=item.get("license", ""),
                ))
        except Exception as exc:
            logger.debug("PyPI search failed: %s", exc)
        return results

    async def get(self, name: str) -> ServerManifest | None:
        """Get a single package from PyPI."""
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
        """Get popular MCP packages from PyPI."""
        return await self.search("mcp-server", limit)


class CompositeRegistry:
    """Aggregates multiple registry backends."""

    def __init__(self, backends: list[RegistryBackend] | None = None) -> None:
        self.backends = backends or []

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search across all backends, deduplicated by name."""
        seen: set[str] = set()
        results: list[ServerManifest] = []
        for backend in self.backends:
            try:
                batch = await backend.search(query, limit)
                for item in batch:
                    if item.name not in seen:
                        seen.add(item.name)
                        results.append(item)
            except Exception:
                continue
        return results[:limit]

    async def get(self, name: str) -> ServerManifest | None:
        """Get a server by name across all backends."""
        for backend in self.backends:
            try:
                result = await backend.get(name)
                if result:
                    return result
            except Exception:
                continue
        return None

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        """Get popular servers across all backends, deduplicated."""
        seen: set[str] = set()
        results: list[ServerManifest] = []
        for backend in self.backends:
            try:
                batch = await backend.popular(limit)
                for item in batch:
                    if item.name not in seen:
                        seen.add(item.name)
                        results.append(item)
            except Exception:
                continue
        return results[:limit]


class RegistryManager:
    """High-level manager that aggregates all registry backends.

    Provides unified search, get, and popular interfaces.
    Auto-creates the three built-in backends if none are provided.
    """

    def __init__(self, backends: list[RegistryBackend] | None = None, client: httpx.AsyncClient | None = None) -> None:
        """Initialize with optional custom backends and HTTP client.

        If no backends are given, creates the three default backends:
        MCP.so, GitHub Registry, and Smithery.
        """
        self._client = client
        if backends:
            self.backends = backends
        else:
            self.backends = [
                BuiltInBackend(),
                McpSoBackend(client=client),
                GitHubRegistryBackend(client=client),
                SmitheryBackend(client=client),
                NpmRegistryBackend(client=client),
                PyPIRegistryBackend(client=client),
            ]
        self._composite = CompositeRegistry(self.backends)

    async def search(self, query: str, limit: int = 20) -> list[ServerManifest]:
        """Search for MCP servers across all backends."""
        return await self._composite.search(query, limit)

    async def get(self, name: str) -> ServerManifest | None:
        """Get detailed info about a specific MCP server."""
        return await self._composite.get(name)

    async def popular(self, limit: int = 20) -> list[ServerManifest]:
        """Get popular MCP servers across all backends."""
        return await self._composite.popular(limit)

    async def close(self) -> None:
        """Close the underlying HTTP client if we own it."""
        if self._client is not None:
            await self._client.aclose()

    async def __aenter__(self) -> RegistryManager:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
