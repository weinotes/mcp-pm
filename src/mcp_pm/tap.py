# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""Tap system — third-party MCP server repositories.

Inspired by Homebrew taps. A tap is a Git repository containing
a ``catalog.yaml`` (or ``servers/`` directory with individual formula files)
that provides additional MCP servers beyond the built-in catalog.

Tap directory structure::

    ~/.mcp-pm/taps/
        <owner>--<repo>/      # e.g. weinotes--mcp-tap
            catalog.yaml      # Optional: curated server list
            formula.yaml      # Optional: single-server formula

Usage::

    mcp-pm tap add weinotes/mcp-tap     # Clone a tap from GitHub
    mcp-pm tap list                       # List installed taps
    mcp-pm tap remove weinotes/mcp-tap   # Remove a tap

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_TAPS_DIR = Path.home() / ".mcp-pm" / "taps"

# ── Tap record ────────────────────────────────────────────────────────────


class Tap:
    """Represents an installed tap (third-party repo)."""

    def __init__(self, name: str, repo_url: str, path: Path) -> None:
        self.name = name            # e.g. "weinotes/mcp-tap"
        self.repo_url = repo_url    # e.g. "https://github.com/weinotes/mcp-tap"
        self.path = path            # Local path under ~/.mcp-pm/taps/

    @property
    def short_name(self) -> str:
        """Return the tap's short name (last path component)."""
        return self.name.split("/")[-1] if "/" in self.name else self.name


# ── TapManager ────────────────────────────────────────────────────────────


class TapManager:
    """Manages third-party tap repositories."""

    def __init__(self, taps_dir: Path | None = None) -> None:
        self.taps_dir = taps_dir or _TAPS_DIR
        self._index_path = self.taps_dir / "_index.yaml"

    # ── Metadata index ───────────────────────────────────────────────────

    def _read_index(self) -> dict[str, dict[str, Any]]:
        """Read the tap index file."""
        if not self._index_path.exists():
            return {}
        try:
            raw = yaml.safe_load(self._index_path.read_text(encoding="utf-8"))
            return raw or {}
        except Exception:
            return {}

    def _write_index(self, index: dict[str, dict[str, Any]]) -> None:
        """Write the tap index file."""
        self.taps_dir.mkdir(parents=True, exist_ok=True)
        self._index_path.write_text(
            yaml.dump(index, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    # ── CRUD ─────────────────────────────────────────────────────────────

    def list_taps(self) -> list[Tap]:
        """List all installed taps."""
        index = self._read_index()
        taps: list[Tap] = []
        for name, info in index.items():
            tap_path = Path(info.get("path", ""))
            if tap_path.exists():
                taps.append(Tap(
                    name=name,
                    repo_url=info.get("repo_url", ""),
                    path=tap_path,
                ))
        return taps

    def get_tap(self, name: str) -> Tap | None:
        """Get a single tap by name."""
        for tap in self.list_taps():
            if tap.name == name or tap.short_name == name:
                return tap
        return None

    async def add(self, name: str, repo_url: str | None = None) -> Tap:
        """Add (clone) a tap from a GitHub repository.

        Args:
            name: Tap name in ``owner/repo`` format.
            repo_url: Full Git URL. Auto-derived from name if omitted.

        Returns:
            The new Tap instance.

        Raises:
            ValueError: If the tap name format is invalid or tap already exists.
        """
        # Validate name format
        if "/" not in name:
            raise ValueError(
                f"Invalid tap name '{name}'. Use 'owner/repo' format, "
                f"e.g. 'weinotes/mcp-tap'"
            )

        # Check if already installed
        existing = self.get_tap(name)
        if existing is not None:
            raise ValueError(f"Tap '{name}' is already installed at {existing.path}")

        # Derive URL if not provided
        if repo_url is None:
            repo_url = f"https://github.com/{name}.git"

        # Derive local path
        safe_name = name.replace("/", "--")
        tap_path = self.taps_dir / safe_name

        logger.info("Cloning tap %s from %s ...", name, repo_url)

        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth", "1", repo_url, str(tap_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=30.0,
            )
            if proc.returncode != 0:
                stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
                raise ValueError(f"git clone failed: {stderr[:300]}")
        except TimeoutError:
            raise ValueError(f"git clone timed out for {repo_url}") from None

        # Record in index
        index = self._read_index()
        index[name] = {
            "repo_url": repo_url,
            "path": str(tap_path),
        }
        self._write_index(index)

        logger.info("Tap '%s' installed at %s", name, tap_path)
        return Tap(name=name, repo_url=repo_url, path=tap_path)

    def remove(self, name: str) -> bool:
        """Remove an installed tap.

        Returns True if removed, False if not found.
        """
        index = self._read_index()
        if name not in index:
            # Try matching by short_name
            for k in index:
                if k.split("/")[-1] == name or k == name:
                    name = k
                    break
            else:
                return False

        tap_path = Path(index[name].get("path", ""))
        if tap_path.exists():
            import shutil
            shutil.rmtree(tap_path, ignore_errors=True)

        del index[name]
        self._write_index(index)
        logger.info("Removed tap '%s'", name)
        return True

    # ── Server discovery from taps ───────────────────────────────────────

    def load_tap_servers(self) -> list[dict[str, Any]]:
        """Load all server entries from all installed taps.

        Scans each tap's ``catalog.yaml`` and individual ``formula.yaml`` files.
        """
        entries: list[dict[str, Any]] = []
        for tap in self.list_taps():
            # Try catalog.yaml
            catalog_path = tap.path / "catalog.yaml"
            if catalog_path.exists():
                try:
                    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
                    for group in (raw or {}).get("catalog", []):
                        for srv in group.get("servers", []):
                            srv["_tap"] = tap.name
                            entries.append(srv)
                except Exception as exc:
                    logger.debug("Failed to load tap catalog %s: %s", catalog_path, exc)

            # Try individual formula.yaml / manifest.yaml files
            for f in tap.path.glob("*/formula.yaml"):
                try:
                    raw = yaml.safe_load(f.read_text(encoding="utf-8"))
                    if raw and raw.get("name"):
                        raw["_tap"] = tap.name
                        entries.append(raw)
                except Exception:
                    pass

        return entries
