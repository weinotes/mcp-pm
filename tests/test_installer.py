"""
Comprehensive tests for the Installer module.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from mcp_pm.installer import InstallError, Installer, SourceType, _run_cmd
from mcp_pm.registry import ServerManifest


# ── SourceType ────────────────────────────────────────────────────────────────


class TestSourceType:
    """SourceType enum values."""

    def test_values(self) -> None:
        assert SourceType.GIT == "git"
        assert SourceType.NPM == "npm"
        assert SourceType.PIP == "pip"
        assert SourceType.DOCKER == "docker"

    def test_members(self) -> None:
        assert set(SourceType.__members__) == {
            "GIT", "NPM", "PIP", "DOCKER", "UVX", "NPX",
            "GO", "CARGO", "DENO", "BREW",
        }


# ── _run_cmd ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_cmd_success() -> None:
    """_run_cmd returns (0, stdout, stderr) for a successful command."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"hello\nworld", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        rc, stdout, stderr = await _run_cmd(["echo", "hello"])

    assert rc == 0
    assert stdout == "hello\nworld"
    assert stderr == ""
    mock_exec.assert_called_once_with(
        "echo", "hello",
        cwd=None,
        stdout=asyncio.subprocess.PIPE,  # noqa: F821  (asyncio imported at runtime)
        stderr=asyncio.subprocess.PIPE,
    )


@pytest.mark.asyncio
async def test_run_cmd_nonzero_returncode() -> None:
    """_run_cmd captures non-zero return codes."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (b"", b"error message")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        rc, stdout, stderr = await _run_cmd(["false"])

    assert rc == 1
    assert stdout == ""
    assert "error message" in stderr


@pytest.mark.asyncio
async def test_run_cmd_timeout() -> None:
    """_run_cmd returns (-1, '', timeout message) on TimeoutError."""
    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = TimeoutError("timed out")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        rc, stdout, stderr = await _run_cmd(["sleep", "999"], timeout=1)

    assert rc == -1
    assert stdout == ""
    assert "timed out" in stderr.lower()


@pytest.mark.asyncio
async def test_run_cmd_file_not_found() -> None:
    """_run_cmd returns (-2, '', 'Command not found: ...') on FileNotFoundError."""
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
        rc, stdout, stderr = await _run_cmd(["nonexistent_cmd_xyz"])

    assert rc == -2
    assert stdout == ""
    assert "Command not found" in stderr
    assert "nonexistent_cmd_xyz" in stderr


@pytest.mark.asyncio
async def test_run_cmd_generic_exception() -> None:
    """_run_cmd returns (-3, '', failure message) on generic Exception."""

    with patch("asyncio.create_subprocess_exec", side_effect=PermissionError("denied")):
        rc, stdout, stderr = await _run_cmd(["some_cmd"])

    assert rc == -3
    assert stdout == ""
    assert "denied" in stderr


# ── Installer helpers ─────────────────────────────────────────────────────────


@pytest.fixture
def install_dir(tmp_path: Path) -> Path:
    """Temporary install directory for testing."""
    d = tmp_path / "servers"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def installer(install_dir: Path) -> Installer:
    """Installer bound to a temporary install directory."""
    return Installer(install_dir=install_dir)


@pytest.fixture
def git_manifest() -> ServerManifest:
    """Sample git-based ServerManifest."""
    return ServerManifest(
        name="test-git-server",
        description="A git-based test server",
        source_type="git",
        source_url="https://github.com/test/repo.git",
        author="Test Author",
        homepage="https://github.com/test/repo",
    )


@pytest.fixture
def pip_manifest() -> ServerManifest:
    """Sample pip-based ServerManifest."""
    return ServerManifest(
        name="test-pip-server",
        description="A pip-based test server",
        source_type="pip",
        source_url="pip:mcp-server-test",
        author="Test Author",
    )


@pytest.fixture
def pip_manifest_with_version() -> ServerManifest:
    """Sample pip-based ServerManifest with version pin."""
    return ServerManifest(
        name="test-pip-versioned",
        description="Version-pinned pip server",
        source_type="pip",
        source_url="pip:mcp-server-test>=1.0",
        author="Test Author",
    )


# ── Installer.install() ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_install_git_success(
    installer: Installer, install_dir: Path, git_manifest: ServerManifest,
) -> None:
    """Install a git-based server successfully."""
    # Mock _run_cmd for git clone and git rev-parse
    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        if "clone" in cmd:
            # Simulate clone by creating the target dir
            target = cmd[-1]
            Path(target).mkdir(parents=True, exist_ok=True)
            return (0, "Cloning...", "")
        if "rev-parse" in cmd:
            return (0, "abc1234", "")
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.install(git_manifest)

    assert result is True

    target_dir = install_dir / "test-git-server"
    assert target_dir.exists()

    # Verify manifest was written
    manifest_path = target_dir / "manifest.yaml"
    assert manifest_path.exists()
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert data["name"] == "test-git-server"
    assert data["source_type"] == "git"
    assert data["source_url"] == "https://github.com/test/repo.git"
    assert data["version"] == "abc1234"

    # Verify formula was written
    formula_path = target_dir / "formula.yaml"
    assert formula_path.exists()


@pytest.mark.asyncio
async def test_install_pip_success(
    installer: Installer, install_dir: Path, pip_manifest: ServerManifest,
) -> None:
    """Install a pip-based server successfully."""
    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        if "pip" in cmd and "install" in cmd:
            return (
                0,
                "Successfully installed mcp-server-test-1.2.3\n",
                "",
            )
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.install(pip_manifest)

    assert result is True

    target_dir = install_dir / "test-pip-server"
    assert target_dir.exists()

    manifest_data = yaml.safe_load(
        (target_dir / "manifest.yaml").read_text(encoding="utf-8"),
    )
    assert manifest_data["name"] == "test-pip-server"
    assert manifest_data["source_type"] == "pip"
    assert manifest_data["version"] == "1.2.3"


@pytest.mark.asyncio
async def test_install_pip_version_extraction(
    installer: Installer, install_dir: Path, pip_manifest_with_version: ServerManifest,
) -> None:
    """pip install with version-pinned package extracts version correctly."""
    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        return (
            0,
            "Successfully installed mcp-server-test-2.0.0\n",
            "",
        )

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.install(pip_manifest_with_version)

    assert result is True

    manifest_data = yaml.safe_load(
        (install_dir / "test-pip-versioned" / "manifest.yaml").read_text(encoding="utf-8"),
    )
    assert manifest_data["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_install_pip_failure(
    installer: Installer, install_dir: Path, pip_manifest: ServerManifest,
) -> None:
    """Failed pip install raises InstallError and cleans up."""
    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        if "pip" in cmd and "install" in cmd:
            return (1, "", "ERROR: Could not find package")
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.install(pip_manifest)

    assert result is False
    # Target directory should be cleaned up
    assert not (install_dir / "test-pip-server").exists()


@pytest.mark.asyncio
async def test_install_pip_no_package(installer: Installer) -> None:
    """pip install with empty package raises InstallError."""
    manifest = ServerManifest(
        name="no-pkg",
        description="No package",
        source_type="pip",
        source_url="pip:",
    )
    result = await installer.install(manifest)
    assert result is False


@pytest.mark.asyncio
async def test_install_git_no_url(
    installer: Installer, install_dir: Path,
) -> None:
    """git install with no source URL raises InstallError."""
    manifest = ServerManifest(
        name="no-url",
        description="No URL",
        source_type="git",
        source_url="",
    )
    result = await installer.install(manifest)
    assert result is False
    # Should clean up
    assert not (install_dir / "no-url").exists()


@pytest.mark.asyncio
async def test_install_git_failure(
    installer: Installer, install_dir: Path, git_manifest: ServerManifest,
) -> None:
    """Failed git clone raises InstallError and cleans up."""
    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        if "clone" in cmd:
            return (128, "", "fatal: repository not found")
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.install(git_manifest)

    assert result is False
    assert not (install_dir / "test-git-server").exists()


@pytest.mark.asyncio
async def test_install_unsupported_source_type(
    installer: Installer, install_dir: Path,
) -> None:
    """Unsupported source type returns False."""
    manifest = ServerManifest(
        name="unsupported",
        description="Unsupported",
        source_type="docker",
        source_url="some-image",
    )
    result = await installer.install(manifest)
    assert result is False
    assert not (install_dir / "unsupported").exists()


@pytest.mark.asyncio
async def test_install_already_installed(
    installer: Installer, install_dir: Path, git_manifest: ServerManifest,
) -> None:
    """Installing an already-existing server returns False."""
    target_dir = install_dir / "test-git-server"
    target_dir.mkdir(parents=True)

    result = await installer.install(git_manifest)
    assert result is False


# ── Installer.install_git() ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_install_git_auto_post_install(
    installer: Installer, install_dir: Path,
) -> None:
    """install_git runs npm/pip post-install when package.json / requirements.txt exist."""
    manifest = ServerManifest(
        name="with-deps",
        description="Has deps",
        source_type="git",
        source_url="https://github.com/test/with-deps.git",
    )

    call_log: list[list[str]] = []

    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        call_log.append(cmd)
        if "clone" in cmd:
            target = cmd[-1]
            Path(target).mkdir(parents=True, exist_ok=True)
            # Create package.json and requirements.txt to trigger post-install
            (Path(target) / "package.json").write_text("{}", encoding="utf-8")
            (Path(target) / "requirements.txt").write_text("requests", encoding="utf-8")
            return (0, "Cloning...", "")
        if "rev-parse" in cmd:
            return (0, "def5678", "")
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.install(manifest)

    assert result is True

    # Verify both npm install and pip install were called
    npm_calls = [c for c in call_log if "npm" in c and "install" in c and "-C" not in c]
    pip_calls = [c for c in call_log if "pip" in c and "install" in c and "-r" in c]
    assert len(npm_calls) == 1
    assert len(pip_calls) == 1


@pytest.mark.asyncio
async def test_install_git_version_unknown_on_failure(
    installer: Installer, install_dir: Path, git_manifest: ServerManifest,
) -> None:
    """When git rev-parse fails, version is 'unknown'."""
    call_count = 0

    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        nonlocal call_count
        call_count += 1
        if "clone" in cmd:
            target = cmd[-1]
            Path(target).mkdir(parents=True, exist_ok=True)
            return (0, "", "")
        if "rev-parse" in cmd:
            return (1, "", "fatal: not a git repository")
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.install(git_manifest)

    assert result is True
    manifest_data = yaml.safe_load(
        (install_dir / "test-git-server" / "manifest.yaml").read_text(encoding="utf-8"),
    )
    assert manifest_data["version"] == "unknown"


# ── Installer.uninstall() ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_uninstall_existing(installer: Installer, install_dir: Path) -> None:
    """Uninstalling an existing server removes it and returns True."""
    target_dir = install_dir / "my-server"
    target_dir.mkdir(parents=True)
    manifest_data = {
        "name": "my-server",
        "source_type": "git",
        "version": "abc",
    }
    (target_dir / "manifest.yaml").write_text(
        yaml.dump(manifest_data), encoding="utf-8",
    )
    assert target_dir.exists()

    result = await installer.uninstall("my-server")
    assert result is True
    assert not target_dir.exists()


@pytest.mark.asyncio
async def test_uninstall_not_found(installer: Installer) -> None:
    """Uninstalling a non-existent server returns False."""
    result = await installer.uninstall("nonexistent-server")
    assert result is False


@pytest.mark.asyncio
async def test_uninstall_pip_based(installer: Installer, install_dir: Path) -> None:
    """Uninstalling a pip-based server also runs pip uninstall."""
    target_dir = install_dir / "pip-server"
    target_dir.mkdir(parents=True)
    manifest_data = {
        "name": "pip-server",
        "source_type": "pip",
        "package": "mcp-server-test",
    }
    (target_dir / "manifest.yaml").write_text(
        yaml.dump(manifest_data), encoding="utf-8",
    )

    uninstall_called = False

    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        nonlocal uninstall_called
        if "uninstall" in cmd:
            uninstall_called = True
            assert "mcp-server-test" in cmd
            return (0, "", "")
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.uninstall("pip-server")

    assert result is True
    assert uninstall_called, "pip uninstall should have been called"
    assert not target_dir.exists()


@pytest.mark.asyncio
async def test_uninstall_pip_uninstall_failure(
    installer: Installer, install_dir: Path,
) -> None:
    """Pip uninstall failure does not block directory removal."""
    target_dir = install_dir / "pip-server-2"
    target_dir.mkdir(parents=True)
    manifest_data = {
        "name": "pip-server-2",
        "source_type": "pip",
        "package": "mcp-server-test",
    }
    (target_dir / "manifest.yaml").write_text(
        yaml.dump(manifest_data), encoding="utf-8",
    )

    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        if "uninstall" in cmd:
            return (1, "", "WARNING: Package not installed")
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.uninstall("pip-server-2")

    # Should still succeed (directory removed)
    assert result is True
    assert not target_dir.exists()


# ── Installer.update() ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_git_success(installer: Installer, install_dir: Path) -> None:
    """Updating a git-based server runs git pull and updates version."""
    target_dir = install_dir / "git-server"
    target_dir.mkdir(parents=True)
    manifest_data = {
        "name": "git-server",
        "source_type": "git",
        "version": "old-hash",
    }
    (target_dir / "manifest.yaml").write_text(
        yaml.dump(manifest_data), encoding="utf-8",
    )

    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        if "pull" in cmd:
            return (0, "Already up to date.", "")
        if "rev-parse" in cmd:
            return (0, "new-hash", "")
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.update("git-server")

    assert result is True

    updated_manifest = yaml.safe_load(
        (target_dir / "manifest.yaml").read_text(encoding="utf-8"),
    )
    assert updated_manifest["version"] == "new-hash"
    assert "updated_at" in updated_manifest


@pytest.mark.asyncio
async def test_update_git_failure(installer: Installer, install_dir: Path) -> None:
    """Failed git pull raises InstallError and returns False."""
    target_dir = install_dir / "git-server"
    target_dir.mkdir(parents=True)
    manifest_data = {
        "name": "git-server",
        "source_type": "git",
        "version": "old-hash",
    }
    (target_dir / "manifest.yaml").write_text(
        yaml.dump(manifest_data), encoding="utf-8",
    )

    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        if "pull" in cmd:
            return (1, "", "CONFLICT: merge conflict")
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.update("git-server")

    assert result is False


@pytest.mark.asyncio
async def test_update_pip_success(installer: Installer, install_dir: Path) -> None:
    """Updating a pip-based server runs pip install --upgrade."""
    target_dir = install_dir / "pip-server"
    target_dir.mkdir(parents=True)
    manifest_data = {
        "name": "pip-server",
        "source_type": "pip",
        "package": "mcp-server-test",
        "version": "1.0.0",
    }
    (target_dir / "manifest.yaml").write_text(
        yaml.dump(manifest_data), encoding="utf-8",
    )

    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        if "--upgrade" in cmd:
            return (
                0,
                "Successfully installed mcp-server-test-2.0.0\n",
                "",
            )
        return (0, "", "")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.update("pip-server")

    assert result is True

    updated_manifest = yaml.safe_load(
        (target_dir / "manifest.yaml").read_text(encoding="utf-8"),
    )
    assert updated_manifest["version"] == "2.0.0"
    assert "updated_at" in updated_manifest


@pytest.mark.asyncio
async def test_update_pip_failure(installer: Installer, install_dir: Path) -> None:
    """Failed pip --upgrade returns False."""
    target_dir = install_dir / "pip-server"
    target_dir.mkdir(parents=True)
    manifest_data = {
        "name": "pip-server",
        "source_type": "pip",
        "package": "mcp-server-test",
        "version": "1.0.0",
    }
    (target_dir / "manifest.yaml").write_text(
        yaml.dump(manifest_data), encoding="utf-8",
    )

    async def fake_run_cmd(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        return (1, "", "ERROR: Package not found")

    with patch("mcp_pm.installer._run_cmd", side_effect=fake_run_cmd):
        result = await installer.update("pip-server")

    assert result is False


@pytest.mark.asyncio
async def test_update_not_found(installer: Installer) -> None:
    """Updating a non-existent server returns False."""
    result = await installer.update("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_update_no_manifest(installer: Installer, install_dir: Path) -> None:
    """Updating a server without a manifest returns False."""
    target_dir = install_dir / "no-manifest"
    target_dir.mkdir(parents=True)
    # No manifest.yaml written

    result = await installer.update("no-manifest")
    assert result is False


# ── Installer.list_installed() ────────────────────────────────────────────────


def test_list_installed_empty(
    installer: Installer, install_dir: Path,
) -> None:
    """list_installed returns empty list when no servers are installed."""
    result = installer.list_installed()
    assert result == []


def test_list_installed_non_existent_dir(tmp_path: Path) -> None:
    """list_installed returns empty list when install_dir does not exist."""
    installer = Installer(install_dir=tmp_path / "nonexistent")
    result = installer.list_installed()
    assert result == []


def test_list_installed_with_servers(
    installer: Installer, install_dir: Path,
) -> None:
    """list_installed returns manifests sorted by name."""
    # Install server A
    dir_a = install_dir / "server-a"
    dir_a.mkdir()
    (dir_a / "manifest.yaml").write_text(
        yaml.dump({"name": "server-a", "source_type": "git", "version": "1.0"}),
        encoding="utf-8",
    )

    # Install server B
    dir_b = install_dir / "server-b"
    dir_b.mkdir()
    (dir_b / "manifest.yaml").write_text(
        yaml.dump({"name": "server-b", "source_type": "pip", "version": "2.0"}),
        encoding="utf-8",
    )

    result = installer.list_installed()
    assert len(result) == 2
    assert result[0]["name"] == "server-a"
    assert result[1]["name"] == "server-b"
    assert "path" in result[0]
    assert "path" in result[1]


def test_list_installed_without_manifest(
    installer: Installer, install_dir: Path,
) -> None:
    """Directories without manifests are included with 'unknown' source_type."""
    dir_no_manifest = install_dir / "no-manifest"
    dir_no_manifest.mkdir()

    dir_with_manifest = install_dir / "with-manifest"
    dir_with_manifest.mkdir()
    (dir_with_manifest / "manifest.yaml").write_text(
        yaml.dump({"name": "with-manifest", "source_type": "git"}),
        encoding="utf-8",
    )

    result = installer.list_installed()
    # sorted order: "no-manifest" < "with-manifest"
    assert len(result) == 2
    assert result[0]["name"] == "no-manifest"
    assert result[0]["source_type"] == "unknown"
    assert result[1]["name"] == "with-manifest"
    assert result[1]["source_type"] == "git"


def test_list_installed_skips_files(
    installer: Installer, install_dir: Path,
) -> None:
    """Non-directory entries in install_dir are skipped."""
    (install_dir / "some_file.txt").write_text("hello", encoding="utf-8")

    result = installer.list_installed()
    assert result == []


# ── Installer.get_manifest() ──────────────────────────────────────────────────


def test_get_manifest_exists(installer: Installer, install_dir: Path) -> None:
    """get_manifest returns the manifest dict for an installed server."""
    target_dir = install_dir / "test-server"
    target_dir.mkdir()
    manifest_data = {
        "name": "test-server",
        "source_type": "git",
        "version": "abc123",
        "installed_at": "2025-01-01T00:00:00+00:00",
    }
    (target_dir / "manifest.yaml").write_text(
        yaml.dump(manifest_data), encoding="utf-8",
    )

    result = installer.get_manifest("test-server")
    assert result is not None
    assert result["name"] == "test-server"
    assert result["version"] == "abc123"


def test_get_manifest_not_found(installer: Installer) -> None:
    """get_manifest returns None for a non-existent server."""
    result = installer.get_manifest("nonexistent")
    assert result is None


def test_get_manifest_directory_exists_no_manifest(
    installer: Installer, install_dir: Path,
) -> None:
    """get_manifest returns None when directory exists but manifest does not."""
    target_dir = install_dir / "empty-dir"
    target_dir.mkdir()

    result = installer.get_manifest("empty-dir")
    assert result is None


def test_get_manifest_corrupted(installer: Installer, install_dir: Path) -> None:
    """get_manifest returns None for corrupted/invalid YAML."""
    target_dir = install_dir / "corrupted"
    target_dir.mkdir()
    (target_dir / "manifest.yaml").write_text(
        "{invalid: yaml: unclosed", encoding="utf-8",
    )

    result = installer.get_manifest("corrupted")
    assert result is None


# ── Installer.uninstall() running server ──────────────────────────────────────


@pytest.mark.asyncio
async def test_uninstall_removes_directory_regardless(
    installer: Installer, install_dir: Path,
) -> None:
    """Uninstall removes the directory even if read_manifest fails."""
    target_dir = install_dir / "stubborn"
    target_dir.mkdir(parents=True)
    # Write invalid manifest
    (target_dir / "manifest.yaml").write_text(
        "garbage: [unparseable", encoding="utf-8",
    )
    assert target_dir.exists()

    result = await installer.uninstall("stubborn")
    assert result is True
    assert not target_dir.exists()


# ── InstallError ──────────────────────────────────────────────────────────────


def test_install_error() -> None:
    """InstallError is a proper exception."""
    err = InstallError("something went wrong")
    assert str(err) == "something went wrong"
    assert isinstance(err, Exception)
