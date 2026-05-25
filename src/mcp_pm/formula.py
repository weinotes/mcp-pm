# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""Formula system — mcp-pm's equivalent of Homebrew formulae.

A Formula is the metadata definition for an MCP server package.
It extends the basic install manifest with version tracking,
dependency management, health checks, and pinning support.

Formula YAML format (``mcp-formula.yaml``):
    name: str                         # Server name (unique identifier)
    description: str                  # Human-readable description
    source_type: str                  # git | npm | pip | docker
    source_url: str                   # Git URL / npm package / pip package
    homepage: str | None              # Project website
    author: str | None                # Author or organization
    license: str | None               # SPDX license identifier
    tags: list[str]                   # Categorization tags
    tools_count: int                  # Number of MCP tools exposed
    version: str                      # Currently installed version
    version_url: str | None           # URL to check latest version
    checksum: str | None              # SHA-256 of source (git: commit)
    dependencies: list[str]           # Required MCP server names
    pinned: bool                      # If true, skip update/upgrade
    health_check: str | None          # Command to verify server is alive
    install_hint: str | None          # Custom install guide for unsupported types

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Default paths (used when no custom install_dir is provided)
_DEFAULT_INSTALL_DIR = Path.home() / ".mcp-pm" / "servers"


# ── Formula dataclass ─────────────────────────────────────────────────────


@dataclass
class Formula:
    """Formula metadata for an MCP server package."""

    name: str
    description: str = ""
    source_type: str = "git"
    source_url: str = ""
    homepage: str | None = None
    author: str | None = None
    license: str | None = None
    tags: list[str] = field(default_factory=list)
    tools_count: int = 0
    version: str = "unknown"
    version_url: str | None = None
    checksum: str | None = None
    dependencies: list[str] = field(default_factory=list)
    pinned: bool = False
    health_check: str | None = None
    install_hint: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Formula:
        """Create a Formula from a dict (YAML manifest)."""
        return cls(
            name=str(data.get("name", "")),
            description=str(data.get("description", data.get("desc", ""))),
            source_type=str(data.get("source_type", data.get("type", "git"))),
            source_url=str(data.get("source_url", data.get("url", ""))),
            homepage=data.get("homepage"),
            author=data.get("author"),
            license=data.get("license"),
            tags=list(data.get("tags", [])),
            tools_count=int(data.get("tools_count", data.get("tools", 0))),
            version=str(data.get("version", "unknown")),
            version_url=data.get("version_url"),
            checksum=data.get("checksum"),
            dependencies=list(data.get("dependencies", [])),
            pinned=bool(data.get("pinned", False)),
            health_check=data.get("health_check"),
            install_hint=data.get("install_hint"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for YAML output."""
        d: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "source_type": self.source_type,
            "source_url": self.source_url,
        }
        for key in ("homepage", "author", "license", "version_url",
                     "checksum", "health_check", "install_hint"):
            val = getattr(self, key, None)
            if val:
                d[key] = val
        for key in ("tags", "dependencies"):
            val = getattr(self, key, [])
            if val:
                d[key] = list(val)
        if self.tools_count:
            d["tools_count"] = self.tools_count
        if self.version and self.version != "unknown":
            d["version"] = self.version
        if self.pinned:
            d["pinned"] = True
        return d


# ── Legacy path helpers (kept for external callers) ───────────────────────
# Note: FormulaManager methods now use self.install_dir directly.
# These helpers still point to the default ~/.mcp-pm/servers/ location.


def _formula_path(name: str) -> Path:
    """Get formula.yaml path under the default install directory."""
    return _DEFAULT_INSTALL_DIR / name / "formula.yaml"


def _manifest_path(name: str) -> Path:
    """Get manifest.yaml path under the default install directory."""
    return _DEFAULT_INSTALL_DIR / name / "manifest.yaml"


# ── FormulaManager ───────────────────────────────────────────────────────


class FormulaManager:
    """Manages Formula loading, saving, and version checking."""

    def __init__(self, install_dir: Path | None = None) -> None:
        self.install_dir = install_dir or _DEFAULT_INSTALL_DIR

    # ── CRUD ─────────────────────────────────────────────────────────────

    def load(self, name: str) -> Formula | None:
        """Load a Formula from disk (formula.yaml or legacy manifest.yaml)."""
        path = self.install_dir / name / "formula.yaml"
        if path.exists():
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                return Formula.from_dict(raw or {})
            except Exception as exc:
                logger.warning("Failed to load formula for '%s': %s", name, exc)
                return None

        # Fallback: try legacy manifest.yaml
        mpath = self.install_dir / name / "manifest.yaml"
        if mpath.exists():
            try:
                raw = yaml.safe_load(mpath.read_text(encoding="utf-8"))
                return Formula.from_dict(raw or {})
            except Exception as exc:
                logger.debug("Failed to load formula '%s': %s", name, exc)
                return None
        return None

    def save(self, formula: Formula) -> None:
        """Write a Formula to disk as formula.yaml."""
        target_dir = self.install_dir / formula.name
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / "formula.yaml"
        path.write_text(
            yaml.dump(formula.to_dict(), default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def list_formulae(self) -> list[Formula]:
        """List all installed servers as Formulae."""
        if not self.install_dir.exists():
            return []
        formulae: list[Formula] = []
        for entry in sorted(self.install_dir.iterdir()):
            if not entry.is_dir():
                continue
            f = self.load(entry.name)
            if f is not None:
                formulae.append(f)
        return formulae

    def delete(self, name: str) -> bool:
        """Delete the formula file (not the server directory)."""
        path = self.install_dir / name / "formula.yaml"
        if path.exists():
            path.unlink()
            return True
        return False

    # ── Version checking ─────────────────────────────────────────────────

    async def check_latest(self, formula: Formula) -> str | None:
        """Query the latest available version for a formula.

        Returns the latest version string, or None if unavailable.
        Resolution depends on source_type:
        - git:   ``git ls-remote --tags``
        - pip:   PyPI JSON API
        - npm:   npm registry API
        """
        source_type = formula.source_type

        if source_type == "git":
            return await self._latest_git(formula.source_url)

        if source_type == "pip":
            pkg = formula.source_url
            for prefix in ("pip:", "pip install ", "uvx ", "uvx:"):
                if pkg.startswith(prefix):
                    pkg = pkg[len(prefix):]
            return await self._latest_pip(pkg.strip())

        if source_type == "npm":
            return await self._latest_npm(formula.source_url)

        # Fallback: try version_url if set
        if formula.version_url:
            return await self._latest_from_url(formula.version_url)

        return None

    @staticmethod
    async def _latest_git(repo_url: str) -> str | None:
        """Get the latest tag from a git repository."""
        import asyncio
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "ls-remote", "--tags", "--sort=-v:refname", repo_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout_bytes, _ = await asyncio.wait_for(
                proc.communicate(), timeout=10.0,
            )
            lines = stdout_bytes.decode("utf-8").strip().splitlines()
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    ref = parts[-1]
                    tag = ref.replace("refs/tags/", "").rstrip("^{}")
                    if tag and not tag.endswith(".0"):
                        return tag
            return None
        except Exception as exc:
            logger.debug("git ls-remote failed for %s: %s", repo_url, exc)
            return None

    @staticmethod
    async def _latest_pip(package: str) -> str | None:
        """Get the latest version from PyPI."""
        import httpx
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(5.0),
                headers={"Accept": "application/json"},
            ) as client:
                resp = await client.get(f"https://pypi.org/pypi/{package}/json")
                resp.raise_for_status()
                data = resp.json()
                return data.get("info", {}).get("version")
        except Exception as exc:
            logger.debug("PyPI lookup failed for %s: %s", package, exc)
            return None

    @staticmethod
    async def _latest_npm(package: str) -> str | None:
        """Get the latest version from npm registry."""
        import httpx
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(5.0),
                headers={"Accept": "application/json"},
            ) as client:
                resp = await client.get(
                    f"https://registry.npmjs.org/{package.replace('/', '%2F')}/latest",
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("version")
        except Exception as exc:
            logger.debug("npm lookup failed for %s: %s", package, exc)
            return None

    @staticmethod
    async def _latest_from_url(url: str) -> str | None:
        """Fetch latest version from a custom URL."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text.strip()
        except Exception as exc:
            logger.debug("Version URL fetch failed for %s: %s", url, exc)
            return None

    @staticmethod
    def compare_versions(current: str, latest: str | None) -> str | None:
        """Compare current vs. latest version.

        Returns ``"outdated"``, ``"ahead"``, ``"current"``, or ``None`` (unknown).
        Handles SemVer (``1.2.3``), git hashes (``abc1234``), and date stamps.
        """
        if not latest or latest == "unknown":
            return None
        if current == latest:
            return "current"

        # Try SemVer comparison
        def _parse_semver(v: str) -> tuple[int, ...] | None:
            parts = v.strip().lstrip("vV").split(".")
            try:
                return tuple(int(p) for p in parts[:3])
            except (ValueError, IndexError):
                return None

        cur_ver = _parse_semver(current)
        lat_ver = _parse_semver(latest)

        if cur_ver is not None and lat_ver is not None:
            if lat_ver > cur_ver:
                return "outdated"
            elif lat_ver < cur_ver:
                return "ahead"
            return "current"

        # For non-SemVer (git hashes, etc), assume different
        return "outdated" if current != latest else "current"
