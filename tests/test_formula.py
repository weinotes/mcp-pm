"""
Tests for the Formula system — mcp-pm's equivalent of Homebrew formulae.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import yaml

from mcp_pm.formula import Formula, FormulaManager


# ── Formula dataclass tests ──────────────────────────────────────────────


class TestFormulaDataclass:
    """Unit tests for Formula dataclass creation and serialization."""

    def test_minimal_formula(self) -> None:
        """Create a Formula with only required fields."""
        f = Formula(name="test-server")
        assert f.name == "test-server"
        assert f.description == ""
        assert f.source_type == "git"
        assert f.tools_count == 0
        assert f.pinned is False
        assert f.version == "unknown"

    def test_full_formula(self) -> None:
        """Create a Formula with all fields."""
        f = Formula(
            name="full-server",
            description="A full server",
            source_type="pip",
            source_url="https://pypi.org/project/test",
            homepage="https://example.com",
            author="Test Author",
            license="MIT",
            tags=["test", "demo"],
            tools_count=5,
            version="1.2.3",
            version_url="https://pypi.org/pypi/test/json",
            checksum="abc123",
            dependencies=["dep-a", "dep-b"],
            pinned=True,
            health_check="curl localhost:8080/health",
            install_hint="Run pip install test",
        )
        assert f.name == "full-server"
        assert f.version == "1.2.3"
        assert f.pinned is True
        assert f.dependencies == ["dep-a", "dep-b"]

    def test_from_dict_standard(self) -> None:
        """Create from standard dict keys."""
        f = Formula.from_dict({
            "name": "std-server",
            "description": "Standard keys",
            "source_type": "npm",
            "source_url": "npm:@org/pkg",
            "version": "2.0.0",
            "tags": ["npm"],
            "pinned": True,
        })
        assert f.name == "std-server"
        assert f.source_type == "npm"
        assert f.version == "2.0.0"
        assert f.pinned is True

    def test_from_dict_legacy_aliases(self) -> None:
        """Create from legacy alias keys (desc, type, url, tools)."""
        f = Formula.from_dict({
            "name": "legacy-server",
            "desc": "Legacy description",
            "type": "pip",
            "url": "https://pypi.org/project/test",
            "tools": 3,
        })
        assert f.description == "Legacy description"
        assert f.source_type == "pip"
        assert f.source_url == "https://pypi.org/project/test"
        assert f.tools_count == 3

    def test_from_dict_empty(self) -> None:
        """Create from empty dict returns default formula."""
        f = Formula.from_dict({})
        assert f.name == ""
        assert f.description == ""
        assert f.version == "unknown"

    def test_to_dict_basic(self) -> None:
        """Serialize a basic formula to dict (omits defaults)."""
        f = Formula(name="test", description="A test", source_type="git", source_url="https://a")
        d = f.to_dict()
        assert d["name"] == "test"
        assert d["description"] == "A test"
        assert "version" not in d  # "unknown" is omitted
        assert "pinned" not in d   # False is omitted
        assert "tags" not in d     # empty list omitted

    def test_to_dict_full(self) -> None:
        """Serialize a full formula includes all non-default fields."""
        f = Formula(
            name="full",
            description="Full",
            source_type="pip",
            source_url="https://p",
            homepage="https://h",
            author="Auth",
            license="MIT",
            tags=["tag1"],
            tools_count=3,
            version="1.0.0",
            pinned=True,
            checksum="sha256:abc",
        )
        d = f.to_dict()
        assert d["version"] == "1.0.0"
        assert d["pinned"] is True
        assert d["tags"] == ["tag1"]
        assert d["tools_count"] == 3
        assert d["checksum"] == "sha256:abc"
        assert d["homepage"] == "https://h"

    def test_to_from_dict_roundtrip(self) -> None:
        """Round-trip to_dict -> from_dict preserves all meaningful fields."""
        original = Formula(
            name="roundtrip",
            description="Goes around",
            source_type="git",
            source_url="https://github.com/user/repo",
            homepage="https://github.com/user/repo",
            author="User",
            license="Apache-2.0",
            tags=["a", "b"],
            tools_count=7,
            version="0.5.0",
            checksum="def456",
            dependencies=["dep1"],
            pinned=True,
        )
        rebuilt = Formula.from_dict(original.to_dict())
        assert rebuilt.name == original.name
        assert rebuilt.source_type == original.source_type
        assert rebuilt.version == original.version
        assert rebuilt.pinned == original.pinned
        assert rebuilt.tools_count == original.tools_count


# ── FormulaManager tests ────────────────────────────────────────────────


class TestFormulaManager:
    """Tests for FormulaManager CRUD and version checking."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Save a formula then load it back."""
        install_dir = tmp_path / "servers"
        mgr = FormulaManager(install_dir=install_dir)
        f = Formula(name="svld", description="Save Load", source_type="pip", source_url="pkg")
        mgr.save(f)

        loaded = mgr.load("svld")
        assert loaded is not None
        assert loaded.name == "svld"
        assert loaded.description == "Save Load"
        assert loaded.source_type == "pip"

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        """Loading nonexistent formula returns None."""
        mgr = FormulaManager(install_dir=tmp_path / "servers")
        assert mgr.load("nonexistent") is None

    def test_load_legacy_manifest(self, tmp_path: Path) -> None:
        """Load from legacy manifest.yaml when formula.yaml absent."""
        install_dir = tmp_path / "servers"
        server_dir = install_dir / "legacy-srv"
        server_dir.mkdir(parents=True)
        manifest = {"name": "legacy-srv", "desc": "Legacy", "type": "npm", "url": "npm:pkg"}
        (server_dir / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")

        mgr = FormulaManager(install_dir=install_dir)
        loaded = mgr.load("legacy-srv")
        assert loaded is not None
        assert loaded.name == "legacy-srv"
        assert loaded.description == "Legacy"
        assert loaded.source_type == "npm"

    def test_load_corrupted_yaml(self, tmp_path: Path) -> None:
        """Loading corrupted YAML returns None gracefully."""
        install_dir = tmp_path / "servers"
        server_dir = install_dir / "corrupted"
        server_dir.mkdir(parents=True)
        (server_dir / "formula.yaml").write_text("{invalid: yaml: [}", encoding="utf-8")

        mgr = FormulaManager(install_dir=install_dir)
        assert mgr.load("corrupted") is None

    def test_delete_formula(self, tmp_path: Path) -> None:
        """Delete formula file returns True and file is gone."""
        install_dir = tmp_path / "servers"
        mgr = FormulaManager(install_dir=install_dir)
        f = Formula(name="to-delete", description="Delete me", source_type="git", source_url="https://x")
        mgr.save(f)
        assert (install_dir / "to-delete" / "formula.yaml").exists()

        result = mgr.delete("to-delete")
        assert result is True
        assert not (install_dir / "to-delete" / "formula.yaml").exists()

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        """Deleting nonexistent formula returns False."""
        mgr = FormulaManager(install_dir=tmp_path / "servers")
        assert mgr.delete("ghost") is False

    def test_list_formulae_empty(self, tmp_path: Path) -> None:
        """Empty install dir returns empty list."""
        mgr = FormulaManager(install_dir=tmp_path / "servers")
        assert mgr.list_formulae() == []

    def test_list_formulae(self, tmp_path: Path) -> None:
        """Non-empty install dir returns all valid formulae."""
        install_dir = tmp_path / "servers"
        mgr = FormulaManager(install_dir=install_dir)
        for name in ("alpha", "beta", "gamma"):
            mgr.save(Formula(name=name, description=f"Server {name}", source_type="git", source_url=f"https://{name}"))
        results = mgr.list_formulae()
        assert len(results) == 3
        names = [f.name for f in results]
        assert names == ["alpha", "beta", "gamma"]  # sorted

    def test_list_formulae_skip_non_dirs(self, tmp_path: Path) -> None:
        """Non-directory entries in install dir are skipped."""
        install_dir = tmp_path / "servers"
        mgr = FormulaManager(install_dir=install_dir)
        mgr.save(Formula(name="valid", description="Valid", source_type="git", source_url="https://v"))
        # Add a file that looks like a directory entry but isn't
        (install_dir / "not-a-dir.txt").write_text("hi", encoding="utf-8")
        results = mgr.list_formulae()
        assert len(results) == 1
        assert results[0].name == "valid"

    @staticmethod
    def _make_httpx_mock(json_data: dict, status_code: int = 200) -> MagicMock:
        """Create a mock for httpx.AsyncClient used as async context manager."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data
        if status_code < 400:
            mock_resp.raise_for_status.return_value = None
        else:
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_resp
            )

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)  # await client.get()

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)  # await ctx.__aenter__
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        return mock_ctx

    @pytest.mark.asyncio
    async def test_check_latest_git(self) -> None:
        """git source queries ls-remote and parses tags."""
        mgr = FormulaManager()
        f = Formula(name="git-srv", source_type="git", source_url="https://github.com/user/repo")

        # git ls-remote output format: <sha>\t<ref>
        git_output = (
            b"abc123\trefs/tags/v2.0.0\n"
            b"def456\trefs/tags/v1.2.3\n"
            b"ghi789\trefs/tags/v1.0.0\n"
        )
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(git_output, b""))

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
            latest = await mgr.check_latest(f)
            # `--sort=-v:refname` sorts descending, so first non-.0 tag should be returned
            assert latest is not None

    @pytest.mark.asyncio
    async def test_check_latest_pip(self) -> None:
        """pip source queries PyPI JSON API."""
        mgr = FormulaManager()
        f = Formula(name="pip-srv", source_type="pip", source_url="requests")

        with patch("httpx.AsyncClient", return_value=self._make_httpx_mock(
            {"info": {"version": "2.31.0"}}
        )):
            latest = await mgr.check_latest(f)
            assert latest == "2.31.0"

    @pytest.mark.asyncio
    async def test_check_latest_pip_strips_prefix(self) -> None:
        """pip source strips 'pip:' prefix before querying."""
        mgr = FormulaManager()
        f = Formula(name="pip-prefix", source_type="pip", source_url="pip:requests")

        called_url = None

        orig_ctx = self._make_httpx_mock({"info": {"version": "2.31.0"}})
        # get the underlying mock_client
        mock_client = orig_ctx.__aenter__.return_value

        async def capture_url(url, *args, **kwargs):
            nonlocal called_url
            called_url = url
            return mock_client.get.return_value

        mock_client.get.side_effect = capture_url

        with patch("httpx.AsyncClient", return_value=orig_ctx):
            latest = await mgr.check_latest(f)
            assert latest == "2.31.0"
            assert "requests" in called_url
            assert "pip:" not in called_url

    @pytest.mark.asyncio
    async def test_check_latest_npm(self) -> None:
        """npm source queries npm registry API."""
        mgr = FormulaManager()
        f = Formula(name="npm-srv", source_type="npm", source_url="express")

        with patch("httpx.AsyncClient", return_value=self._make_httpx_mock(
            {"version": "4.18.2"}
        )):
            latest = await mgr.check_latest(f)
            assert latest == "4.18.2"

    @pytest.mark.asyncio
    async def test_check_latest_unknown_source(self) -> None:
        """Unknown source type returns None."""
        mgr = FormulaManager()
        f = Formula(name="unknown-srv", source_type="docker", source_url="ubuntu:latest")
        latest = await mgr.check_latest(f)
        assert latest is None

    @pytest.mark.asyncio
    async def test_check_latest_pip_not_found(self) -> None:
        """PyPI 404 returns None."""
        mgr = FormulaManager()
        f = Formula(name="missing", source_type="pip", source_url="nonexistent-package-xyz")

        with patch("httpx.AsyncClient", return_value=self._make_httpx_mock({}, status_code=404)):
            latest = await mgr.check_latest(f)
            assert latest is None
