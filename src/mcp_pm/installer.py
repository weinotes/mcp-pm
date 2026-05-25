# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""
Installer engine — handles installing, uninstalling, and updating MCP servers.

Supports multiple source types:
  - git: clone from git repository
  - npm: install via npm/git
  - pip: install Python packages
  - docker: pull docker images

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import sys
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from .registry import ServerManifest

logger = logging.getLogger(__name__)


class SourceType(StrEnum):
    GIT = "git"
    NPM = "npm"
    PIP = "pip"
    DOCKER = "docker"


class InstallError(Exception):
    """Raised when an installation step fails."""


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()


async def _run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 300,
) -> tuple[int, str, str]:
    """Run a subprocess command asynchronously.

    Returns (returncode, stdout, stderr).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        return (proc.returncode or 0, stdout, stderr)
    except TimeoutError:
        return (-1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}")
    except FileNotFoundError:
        return (-2, "", f"Command not found: {cmd[0]}")
    except Exception as exc:
        return (-3, "", f"Failed to run command: {exc}")


def _write_manifest(manifest_dir: Path, data: dict[str, Any]) -> None:
    """Write installation manifest YAML to the server directory."""
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "manifest.yaml"
    manifest_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _write_formula(manifest_dir: Path, data: dict[str, Any]) -> None:
    """Write formula.yaml alongside manifest.yaml for Homebrew-compatible metadata."""
    from mcp_pm.formula import Formula

    formula = Formula.from_dict(data)
    formula_path = manifest_dir / "formula.yaml"
    formula_path.write_text(
        yaml.dump(formula.to_dict(), default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _read_manifest(manifest_dir: Path) -> dict[str, Any] | None:
    """Read installation manifest YAML from the server directory."""
    manifest_path = manifest_dir / "manifest.yaml"
    if not manifest_path.exists():
        return None
    try:
        raw = manifest_path.read_text(encoding="utf-8")
        return yaml.safe_load(raw) or {}
    except Exception as exc:
        logger.debug("Failed to load manifest %s: %s", manifest_path, exc)
        return None


class Installer:
    """Manages installation, uninstallation, and updates of MCP servers.

    Each installed server lives in ``install_dir/{name}/`` with a
    ``manifest.yaml`` recording metadata.
    """

    def __init__(self, install_dir: Path | None = None) -> None:
        self.install_dir = install_dir or Path.home() / ".mcp-pm" / "servers"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def install(self, manifest: ServerManifest) -> bool:
        """Install an MCP server based on its ``source_type``.

        Returns ``True`` on success, ``False`` on failure.
        """
        target_dir = self.install_dir / manifest.name
        if target_dir.exists():
            logger.warning("Server '%s' already installed at %s", manifest.name, target_dir)
            return False

        try:
            if manifest.source_type == SourceType.GIT.value:
                result = await self.install_git(manifest)
            elif manifest.source_type == SourceType.PIP.value:
                result = await self.install_pip(manifest)
            else:
                logger.error("Unsupported source type: %s", manifest.source_type)
                return False

            if result is not None:
                logger.info("Installed '%s' at %s", manifest.name, result)
                return True
            return False
        except InstallError as exc:
            logger.error("Installation of '%s' failed: %s", manifest.name, exc)
            # Clean up partial install
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            return False
        except Exception as exc:
            logger.error("Unexpected error installing '%s': %s", manifest.name, exc)
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            return False

    async def install_git(self, manifest: ServerManifest) -> Path:
        """Clone a git repository into the install directory.

        Returns the target path on success.
        """
        target_dir = self.install_dir / manifest.name
        target_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Cloning %s into %s ...", manifest.source_url, target_dir)

        if not manifest.source_url:
            raise InstallError("No source URL provided for git installation")

        returncode, stdout, stderr = await _run_cmd(
            ["git", "clone", "--depth", "1", manifest.source_url, str(target_dir)],
        )
        if returncode != 0:
            raise InstallError(f"git clone failed (rc={returncode}): {stderr[:500]}")

        # Get the installed version from git
        returncode, ver_out, _ = await _run_cmd(
            ["git", "-C", str(target_dir), "rev-parse", "--short", "HEAD"],
        )
        version = ver_out.strip() if returncode == 0 else "unknown"

        # Optionally run npm/pip install if a lock/requirements file exists
        await self._auto_post_install(target_dir)

        manifest_data: dict[str, Any] = {
            "name": manifest.name,
            "source_type": "git",
            "source_url": manifest.source_url,
            "version": version,
            "installed_at": _now_iso(),
            "description": manifest.description,
            "author": manifest.author,
            "homepage": manifest.homepage or manifest.source_url,
        }
        _write_manifest(target_dir, manifest_data)
        _write_formula(target_dir, manifest_data)
        return target_dir

    async def install_pip(self, manifest: ServerManifest) -> Path:
        """Install a Python package via pip (or uvx if available).

        Returns the target path on success.
        """
        target_dir = self.install_dir / manifest.name
        target_dir.mkdir(parents=True, exist_ok=True)

        package = manifest.source_url
        # Strip common prefixes to get the actual package name
        for prefix in ("pip:", "pip install ", "uvx ", "uvx:"):
            if package.startswith(prefix):
                package = package[len(prefix) :]
        package = package.strip()

        if not package:
            raise InstallError("No package specifier found for pip installation")

        # Normalize package name: strip version specifiers
        pkg_name = package.split("==")[0].split(">=")[0].split("<")[0].strip()

        logger.info("Installing pip package: %s", package)

        cmd = [sys.executable, "-m", "pip", "install", package]

        returncode, stdout, stderr = await _run_cmd(cmd)
        if returncode != 0:
            raise InstallError(f"pip install failed (rc={returncode}): {stderr[:500]}")

        # Extract version from pip output
        # pip output format examples:
        #   Successfully installed mcp-server-weather-0.1.4
        #   Requirement already satisfied: mcp-server-weather in ... (0.1.4)
        version = "unknown"
        for line in stdout.splitlines():
            line = line.strip()
            # Look for "Successfully installed <package>-<version>"
            if "Successfully installed" in line:
                for word in line.split():
                    if pkg_name in word:
                        ver_part = word.split(pkg_name, 1)[-1]
                        if ver_part.startswith("-"):
                            ver_part = ver_part[1:]
                        if ver_part:
                            version = ver_part
                            break
            if version != "unknown":
                break

        manifest_data: dict[str, Any] = {
            "name": manifest.name,
            "source_type": "pip",
            "source_url": manifest.source_url,
            "package": package,
            "version": version,
            "installed_at": _now_iso(),
            "description": manifest.description,
            "author": manifest.author,
            "homepage": manifest.homepage,
        }
        _write_manifest(target_dir, manifest_data)
        _write_formula(target_dir, manifest_data)
        return target_dir

    async def uninstall(self, name: str) -> bool:
        """Remove an installed MCP server directory.

        Returns ``True`` if successfully removed, ``False`` if not found.
        """
        target_dir = self.install_dir / name
        if not target_dir.exists():
            logger.warning("Server '%s' is not installed.", name)
            return False

        # Check if it was installed via pip and offer to uninstall the package
        manifest = _read_manifest(target_dir)
        if manifest and manifest.get("source_type") == "pip":
            package = manifest.get("package", name)
            logger.info("Uninstalling pip package: %s", package)
            uninstall_cmd = [
                sys.executable, "-m", "pip", "uninstall", "-y", package,
            ]
            returncode, _, stderr = await _run_cmd(uninstall_cmd)
            if returncode != 0:
                logger.warning("pip uninstall had issues: %s", stderr[:200])

        shutil.rmtree(target_dir, ignore_errors=True)
        logger.info("Removed '%s' from %s", name, target_dir)
        return not target_dir.exists()

    async def update(self, name: str) -> bool:
        """Update an installed MCP server to the latest version.

        For git sources: ``git pull``.
        For pip sources: ``pip install --upgrade``.
        Returns ``True`` on success, ``False`` on failure or if not found.
        """
        target_dir = self.install_dir / name
        if not target_dir.exists():
            logger.warning("Server '%s' is not installed.", name)
            return False

        manifest = _read_manifest(target_dir)
        if manifest is None:
            logger.warning("No manifest found for '%s', cannot update.", name)
            return False

        source_type = manifest.get("source_type", "git")

        try:
            if source_type == "git":
                return await self._update_git(name, target_dir)
            elif source_type == "pip":
                return await self._update_pip(name, target_dir, manifest)
            else:
                logger.error("Unsupported source type for update: %s", source_type)
                return False
        except InstallError as exc:
            logger.error("Update of '%s' failed: %s", name, exc)
            return False

    def list_installed(self) -> list[dict[str, Any]]:
        """List all installed servers with their metadata.

        Returns a list of dicts, each containing the manifest data plus
        the server directory path.
        """
        if not self.install_dir.exists():
            return []

        result: list[dict[str, Any]] = []
        for entry in sorted(self.install_dir.iterdir()):
            if not entry.is_dir():
                continue
            manifest = _read_manifest(entry)
            if manifest:
                manifest["path"] = str(entry)
                result.append(manifest)
            else:
                # Directory exists but no manifest — still include it
                result.append({
                    "name": entry.name,
                    "path": str(entry),
                    "source_type": "unknown",
                    "source_url": "",
                    "version": "unknown",
                    "installed_at": "",
                })
        return result

    def get_manifest(self, name: str) -> dict[str, Any] | None:
        """Read the installation manifest for a specific server.

        Returns the manifest dict or ``None`` if not installed.
        """
        target_dir = self.install_dir / name
        if not target_dir.exists():
            return None
        return _read_manifest(target_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _auto_post_install(self, target_dir: Path) -> None:
        """Run npm/pip install automatically if standard files are found."""
        # If there's a package.json, run npm install
        if (target_dir / "package.json").exists():
            logger.info("Found package.json, running npm install ...")
            rc, _, stderr = await _run_cmd(["npm", "install"], cwd=target_dir)
            if rc != 0:
                logger.warning("npm install had issues: %s", stderr[:200])

        # If there's a requirements.txt, run pip install -r
        if (target_dir / "requirements.txt").exists():
            logger.info("Found requirements.txt, running pip install ...")
            rc, _, stderr = await _run_cmd(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=target_dir
            )
            if rc != 0:
                logger.warning("pip install -r had issues: %s", stderr[:200])

    async def _update_git(self, name: str, target_dir: Path) -> bool:
        """Update a git-based installation."""
        logger.info("Pulling latest changes for '%s' ...", name)
        returncode, stdout, stderr = await _run_cmd(
            ["git", "-C", str(target_dir), "pull", "--ff-only"],
        )
        if returncode != 0:
            raise InstallError(f"git pull failed (rc={returncode}): {stderr[:500]}")

        # Update version in manifest
        rc, ver_out, _ = await _run_cmd(
            ["git", "-C", str(target_dir), "rev-parse", "--short", "HEAD"],
        )
        version = ver_out.strip() if rc == 0 else "unknown"

        manifest = _read_manifest(target_dir) or {}
        manifest["version"] = version
        manifest["updated_at"] = _now_iso()
        _write_manifest(target_dir, manifest)

        # Re-run post-install steps (in case deps changed)
        await self._auto_post_install(target_dir)
        return True

    async def _update_pip(self, name: str, target_dir: Path, manifest: dict[str, Any]) -> bool:
        """Update a pip-based installation."""
        package = manifest.get("package", name)
        # Normalize package name: strip version specifiers
        pkg_name = package.split("==")[0].split(">=")[0].split("<")[0].strip()
        logger.info("Upgrading pip package: %s", package)

        returncode, stdout, stderr = await _run_cmd(
            [sys.executable, "-m", "pip", "install", "--upgrade", package],
        )
        if returncode != 0:
            raise InstallError(f"pip upgrade failed (rc={returncode}): {stderr[:500]}")

        # Extract new version from pip upgrade output
        version = "unknown"
        for line in stdout.splitlines():
            line_stripped = line.strip()
            # Look for "Successfully installed <package>-<version>"
            if "Successfully installed" in line_stripped:
                for word in line_stripped.split():
                    if pkg_name in word:
                        ver_part = word.split(pkg_name, 1)[-1]
                        if ver_part.startswith("-"):
                            ver_part = ver_part[1:]
                        if ver_part:
                            version = ver_part
                            break
            if version != "unknown":
                break

        manifest["version"] = version
        manifest["updated_at"] = _now_iso()
        _write_manifest(target_dir, manifest)
        return True
