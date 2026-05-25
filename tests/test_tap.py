"""
Tests for the Tap system — third-party MCP server repositories (taps).

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from mcp_pm.tap import Tap, TapManager


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def taps_dir(tmp_path: Path) -> Path:
    """Provide a temporary taps directory for TapManager."""
    return tmp_path / "taps"


@pytest.fixture
def tm(taps_dir: Path) -> TapManager:
    """Return a TapManager bound to the temporary directory."""
    return TapManager(taps_dir=taps_dir)


# ── Tap dataclass tests ────────────────────────────────────────────────────


class TestTapDataclass:
    """Unit tests for the Tap dataclass."""

    def test_tap_creation(self) -> None:
        """Create a Tap instance with standard fields."""
        tap = Tap(
            name="weinotes/mcp-tap",
            repo_url="https://github.com/weinotes/mcp-tap",
            path=Path("/tmp/fake/tap"),
        )
        assert tap.name == "weinotes/mcp-tap"
        assert tap.repo_url == "https://github.com/weinotes/mcp-tap"
        assert tap.path == Path("/tmp/fake/tap")

    def test_short_name(self) -> None:
        """short_name returns the last path component of the tap name."""
        tap = Tap(
            name="weinotes/mcp-tap",
            repo_url="https://github.com/weinotes/mcp-tap",
            path=Path("/tmp/fake/tap"),
        )
        assert tap.short_name == "mcp-tap"

    def test_short_name_no_slash(self) -> None:
        """short_name returns the name as-is when there is no slash."""
        tap = Tap(
            name="simple-tap",
            repo_url="https://github.com/example/simple-tap",
            path=Path("/tmp/fake/tap"),
        )
        assert tap.short_name == "simple-tap"

    def test_short_name_multiple_components(self) -> None:
        """short_name handles names with more than two path components."""
        tap = Tap(
            name="org/group/mcp-tap",
            repo_url="https://github.com/org/group/mcp-tap",
            path=Path("/tmp/fake/tap"),
        )
        assert tap.short_name == "mcp-tap"


# ── TapManager CRUD tests ──────────────────────────────────────────────────


class TestTapManagerList:
    """Tests for TapManager.list_taps()."""

    def test_list_taps_empty(self, tm: TapManager) -> None:
        """list_taps returns an empty list when no taps are installed."""
        taps = tm.list_taps()
        assert taps == []

    def test_list_taps(self, tm: TapManager, taps_dir: Path) -> None:
        """list_taps returns installed taps from the index."""
        # Seed the index with two taps and create their directories
        tap1_path = taps_dir / "owner--repo1"
        tap2_path = taps_dir / "owner--repo2"
        tap1_path.mkdir(parents=True)
        tap2_path.mkdir(parents=True)

        tm._write_index({
            "owner/repo1": {
                "repo_url": "https://github.com/owner/repo1",
                "path": str(tap1_path),
            },
            "owner/repo2": {
                "repo_url": "https://github.com/owner/repo2",
                "path": str(tap2_path),
            },
        })

        taps = tm.list_taps()
        assert len(taps) == 2

        names = {t.name for t in taps}
        assert names == {"owner/repo1", "owner/repo2"}

    def test_list_taps_skips_missing_dirs(self, tm: TapManager, taps_dir: Path) -> None:
        """list_taps skips index entries whose on-disk directory is gone."""
        real_path = taps_dir / "real--tap"
        real_path.mkdir(parents=True)

        tm._write_index({
            "real/tap": {
                "repo_url": "https://github.com/real/tap",
                "path": str(real_path),
            },
            "ghost/tap": {
                "repo_url": "https://github.com/ghost/tap",
                "path": str(taps_dir / "ghost--tap"),  # doesn't exist
            },
        })

        taps = tm.list_taps()
        assert len(taps) == 1
        assert taps[0].name == "real/tap"


class TestTapManagerAdd:
    """Tests for TapManager.add()."""

    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_add_tap(
        self,
        mock_subprocess: AsyncMock,
        tm: TapManager,
        taps_dir: Path,
    ) -> None:
        """add() clones a tap and records it in the index."""
        # Mock a successful git clone
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_subprocess.return_value = mock_proc

        tap = await tm.add("weinotes/mcp-tap")

        assert tap.name == "weinotes/mcp-tap"
        assert tap.repo_url == "https://github.com/weinotes/mcp-tap.git"
        assert tap.path == taps_dir / "weinotes--mcp-tap"

        # Verify it was saved to index
        index = tm._read_index()
        assert "weinotes/mcp-tap" in index
        assert index["weinotes/mcp-tap"]["repo_url"] == "https://github.com/weinotes/mcp-tap.git"

        # Verify git clone was called
        mock_subprocess.assert_called_once()
        args, _ = mock_subprocess.call_args
        assert args[0] == "git"
        assert args[1] == "clone"
        assert args[2] == "--depth"
        assert args[3] == "1"
        assert args[4] == "https://github.com/weinotes/mcp-tap.git"

    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_add_tap_with_custom_url(
        self,
        mock_subprocess: AsyncMock,
        tm: TapManager,
    ) -> None:
        """add() accepts an explicit repo_url."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_subprocess.return_value = mock_proc

        tap = await tm.add(
            "my/tap",
            repo_url="https://gitlab.com/my/tap.git",
        )
        assert tap.repo_url == "https://gitlab.com/my/tap.git"

    @pytest.mark.asyncio
    async def test_add_tap_invalid_name(self, tm: TapManager) -> None:
        """add() raises ValueError for names without a slash."""
        with pytest.raises(ValueError, match="Invalid tap name"):
            await tm.add("invalidname")

    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_add_tap_already_exists(
        self,
        mock_subprocess: AsyncMock,
        tm: TapManager,
        taps_dir: Path,
    ) -> None:
        """add() raises ValueError when the tap is already installed."""
        # Create a pre-existing tap
        tap_path = taps_dir / "existing--tap"
        tap_path.mkdir(parents=True)
        tm._write_index({
            "existing/tap": {
                "repo_url": "https://github.com/existing/tap",
                "path": str(tap_path),
            },
        })

        with pytest.raises(ValueError, match="already installed"):
            await tm.add("existing/tap")

        # Verify git clone was NOT called
        mock_subprocess.assert_not_called()

    @patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_add_tap_git_clone_failure(
        self,
        mock_subprocess: AsyncMock,
        tm: TapManager,
    ) -> None:
        """add() raises ValueError when git clone fails."""
        mock_proc = MagicMock()
        mock_proc.returncode = 128
        mock_proc.communicate = AsyncMock(return_value=(b"", b"fatal: repository not found"))
        mock_subprocess.return_value = mock_proc

        with pytest.raises(ValueError, match="git clone failed"):
            await tm.add("nonexistent/repo")


class TestTapManagerRemove:
    """Tests for TapManager.remove()."""

    def test_remove_tap(self, tm: TapManager, taps_dir: Path) -> None:
        """remove() deletes the tap directory and its index entry."""
        tap_path = taps_dir / "owner--repo"
        tap_path.mkdir(parents=True)
        (tap_path / "catalog.yaml").write_text("catalog: []", encoding="utf-8")

        tm._write_index({
            "owner/repo": {
                "repo_url": "https://github.com/owner/repo",
                "path": str(tap_path),
            },
        })

        result = tm.remove("owner/repo")
        assert result is True

        # Index entry should be gone
        assert "owner/repo" not in tm._read_index()
        # Directory should be removed
        assert not tap_path.exists()

    def test_remove_nonexistent(self, tm: TapManager) -> None:
        """remove() returns False for a tap that is not installed."""
        result = tm.remove("nonexistent/tap")
        assert result is False

    def test_remove_by_short_name(self, tm: TapManager, taps_dir: Path) -> None:
        """remove() works when given the short name instead of full name."""
        tap_path = taps_dir / "owner--repo"
        tap_path.mkdir(parents=True)

        tm._write_index({
            "owner/repo": {
                "repo_url": "https://github.com/owner/repo",
                "path": str(tap_path),
            },
        })

        result = tm.remove("repo")  # short name
        assert result is True
        assert "owner/repo" not in tm._read_index()

    def test_remove_tap_already_gone_from_disk(
        self, tm: TapManager, taps_dir: Path,
    ) -> None:
        """remove() still cleans up the index even if the directory is already gone."""
        # Index references a directory that doesn't exist on disk
        tm._write_index({
            "ghost/tap": {
                "repo_url": "https://github.com/ghost/tap",
                "path": str(taps_dir / "ghost--tap"),
            },
        })

        result = tm.remove("ghost/tap")
        assert result is True
        assert "ghost/tap" not in tm._read_index()


class TestTapManagerGet:
    """Tests for TapManager.get_tap()."""

    def test_get_tap_by_full_name(self, tm: TapManager, taps_dir: Path) -> None:
        """get_tap() returns the tap when looked up by full name."""
        tap_path = taps_dir / "weinotes--mcp-tap"
        tap_path.mkdir(parents=True)

        tm._write_index({
            "weinotes/mcp-tap": {
                "repo_url": "https://github.com/weinotes/mcp-tap",
                "path": str(tap_path),
            },
        })

        tap = tm.get_tap("weinotes/mcp-tap")
        assert tap is not None
        assert tap.name == "weinotes/mcp-tap"
        assert tap.repo_url == "https://github.com/weinotes/mcp-tap"

    def test_get_tap_by_short_name(self, tm: TapManager, taps_dir: Path) -> None:
        """get_tap() returns the tap when looked up by short name."""
        tap_path = taps_dir / "weinotes--mcp-tap"
        tap_path.mkdir(parents=True)

        tm._write_index({
            "weinotes/mcp-tap": {
                "repo_url": "https://github.com/weinotes/mcp-tap",
                "path": str(tap_path),
            },
        })

        tap = tm.get_tap("mcp-tap")  # short name
        assert tap is not None
        assert tap.name == "weinotes/mcp-tap"

    def test_get_tap_not_found(self, tm: TapManager) -> None:
        """get_tap() returns None for a tap that doesn't exist."""
        tap = tm.get_tap("does/not-exist")
        assert tap is None


class TestTapManagerLoadServers:
    """Tests for TapManager.load_tap_servers()."""

    def test_search_taps_empty(self, tm: TapManager) -> None:
        """load_tap_servers returns an empty list when no taps are installed."""
        servers = tm.load_tap_servers()
        assert servers == []

    def test_search_taps_catalog(self, tm: TapManager, taps_dir: Path) -> None:
        """load_tap_servers reads server entries from catalog.yaml."""
        tap_path = taps_dir / "weinotes--mcp-tap"
        tap_path.mkdir(parents=True)

        catalog = {
            "catalog": [
                {
                    "category": "Development",
                    "servers": [
                        {"name": "server-a", "command": "uvx", "args": ["tool-a"]},
                        {"name": "server-b", "command": "uvx", "args": ["tool-b"]},
                    ],
                },
            ],
        }
        (tap_path / "catalog.yaml").write_text(
            yaml.dump(catalog), encoding="utf-8",
        )

        tm._write_index({
            "weinotes/mcp-tap": {
                "repo_url": "https://github.com/weinotes/mcp-tap",
                "path": str(tap_path),
            },
        })

        servers = tm.load_tap_servers()
        assert len(servers) == 2
        assert servers[0]["name"] == "server-a"
        assert servers[0]["_tap"] == "weinotes/mcp-tap"
        assert servers[1]["name"] == "server-b"
        assert servers[1]["_tap"] == "weinotes/mcp-tap"

    def test_search_taps_formula_files(self, tm: TapManager, taps_dir: Path) -> None:
        """load_tap_servers reads individual formula.yaml files."""
        tap_path = taps_dir / "owner--formula-tap"
        tap_path.mkdir(parents=True)

        # Create a subdirectory with a formula.yaml
        server_dir = tap_path / "my-server"
        server_dir.mkdir()
        formula = {
            "name": "my-server",
            "description": "A custom server",
            "command": "python",
            "args": ["-m", "my_server"],
        }
        (server_dir / "formula.yaml").write_text(
            yaml.dump(formula), encoding="utf-8",
        )

        tm._write_index({
            "owner/formula-tap": {
                "repo_url": "https://github.com/owner/formula-tap",
                "path": str(tap_path),
            },
        })

        servers = tm.load_tap_servers()
        assert len(servers) == 1
        assert servers[0]["name"] == "my-server"
        assert servers[0]["_tap"] == "owner/formula-tap"

    def test_search_taps_multiple_taps(self, tm: TapManager, taps_dir: Path) -> None:
        """load_tap_servers aggregates servers from multiple taps."""
        # Tap 1
        tap1_path = taps_dir / "alice--tap-a"
        tap1_path.mkdir(parents=True)
        (tap1_path / "catalog.yaml").write_text(
            yaml.dump({
                "catalog": [{"category": "Tools", "servers": [{"name": "tool-x"}]}],
            }),
            encoding="utf-8",
        )

        # Tap 2
        tap2_path = taps_dir / "bob--tap-b"
        tap2_path.mkdir(parents=True)
        (tap2_path / "catalog.yaml").write_text(
            yaml.dump({
                "catalog": [{"category": "Tools", "servers": [{"name": "tool-y"}]}],
            }),
            encoding="utf-8",
        )

        tm._write_index({
            "alice/tap-a": {
                "repo_url": "https://github.com/alice/tap-a",
                "path": str(tap1_path),
            },
            "bob/tap-b": {
                "repo_url": "https://github.com/bob/tap-b",
                "path": str(tap2_path),
            },
        })

        servers = tm.load_tap_servers()
        assert len(servers) == 2
        names = {s["name"] for s in servers}
        assert names == {"tool-x", "tool-y"}
