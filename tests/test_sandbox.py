"""
Tests for the sandbox module.

Covers all three isolation levels (off, subprocess, docker) with
mocked subprocess execution.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_pm.exceptions import SandboxError
from mcp_pm.sandbox import SandboxLevel, SandboxManager


class MockProcess:
    """A mock async subprocess.Process that can simulate running/finished."""

    def __init__(self, pid: int = 12345, returncode: int | None = None):
        self.pid = pid
        self._returncode = returncode
        self._waited = False

    @property
    def returncode(self) -> int | None:
        return self._returncode

    async def wait(self) -> int:
        self._waited = True
        return self._returncode or 0

    async def communicate(self) -> tuple[bytes, bytes]:
        return (b"", b"")

    def kill(self) -> None:
        self._returncode = -9

    def terminate(self) -> None:
        self._returncode = -15

    def send_signal(self, sig: int) -> None:
        self._returncode = -sig


@pytest.fixture
def sandbox_off() -> SandboxManager:
    return SandboxManager(level=SandboxLevel.OFF)


@pytest.fixture
def sandbox_subprocess() -> SandboxManager:
    return SandboxManager(level=SandboxLevel.SUBPROCESS)


@pytest.fixture
def sandbox_docker() -> SandboxManager:
    return SandboxManager(level=SandboxLevel.DOCKER)


# ── OFF level ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_off_start_stop(sandbox_off: SandboxManager) -> None:
    """OFF level: start creates Popen process, stop kills it."""
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.returncode = None

    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        pid = await sandbox_off.start("test-server", ["sleep", "10"])
        assert pid == 12345
        mock_popen.assert_called_once()

    # Stop
    with (
        patch("os.kill") as mock_kill,
        patch("os.waitpid"),
    ):
        await sandbox_off.stop(pid)
        mock_kill.assert_called_once_with(pid, 15)  # SIGTERM


@pytest.mark.asyncio
async def test_off_health_alive(sandbox_off: SandboxManager) -> None:
    """OFF level: health returns True for running process."""
    mock_proc = MagicMock()
    mock_proc.pid = 12346
    mock_proc.returncode = None

    with patch("subprocess.Popen", return_value=mock_proc):
        pid = await sandbox_off.start("test", ["sleep", "10"])

    with patch("os.kill", return_value=None):
        healthy = await sandbox_off.health(pid)
        assert healthy is True


@pytest.mark.asyncio
async def test_off_health_dead(sandbox_off: SandboxManager) -> None:
    """OFF level: health returns False when process not tracked."""
    with patch("os.kill", side_effect=ProcessLookupError):
        healthy = await sandbox_off.health(99999)
        assert healthy is False


# ── SUBPROCESS level ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subprocess_start_stop(sandbox_subprocess: SandboxManager) -> None:
    """SUBPROCESS level: start/stop full lifecycle."""
    mock_proc = MockProcess(pid=12347)

    with (
        patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)),
        patch("os.getpgid", return_value=555),
        patch("os.killpg") as mock_killpg,
        patch("os.kill"),
        patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        pid = await sandbox_subprocess.start("test-sub", ["echo", "hello"])
        assert pid == 12347

        await sandbox_subprocess.stop(pid)
        # killpg called for SIGTERM (15) and SIGKILL (9) on process group
        assert mock_killpg.call_count == 2
        # First call: SIGTERM to process group
        killpg_call_1 = mock_killpg.call_args_list[0]
        assert killpg_call_1[0][1] == 15  # SIGTERM
        # Second call: SIGKILL to process group (timeout fallback)
        killpg_call_2 = mock_killpg.call_args_list[1]
        assert killpg_call_2[0][1] == 9  # SIGKILL


@pytest.mark.asyncio
async def test_subprocess_start_command_not_found(sandbox_subprocess: SandboxManager) -> None:
    """SUBPROCESS level: non-existent command raises SandboxError."""
    with (
        patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError),
        pytest.raises(SandboxError, match="Command not found"),
    ):
        await sandbox_subprocess.start("bad-cmd", ["nonexistent_cmd_xyz"])


@pytest.mark.asyncio
async def test_subprocess_health_alive(sandbox_subprocess: SandboxManager) -> None:
    """SUBPROCESS level: health returns True if process exists in tracking."""
    mock_proc = MockProcess(pid=12349)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        pid = await sandbox_subprocess.start("healthy", ["true"])

    with patch("os.kill", return_value=None):
        healthy = await sandbox_subprocess.health(pid)
        assert healthy is True


# ── DOCKER level ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_docker_start(sandbox_docker: SandboxManager) -> None:
    """DOCKER level: start runs docker through create_subprocess_exec."""
    mock_proc = MockProcess(pid=12350)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        pid = await sandbox_docker.start("test-docker", ["docker", "run", "--rm", "my-server"])
        assert pid == 12350


# ── Error handling ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stop_unknown_pid(sandbox_off: SandboxManager) -> None:
    """Stopping untracked PID raises SandboxError."""
    with pytest.raises(SandboxError, match="No sandbox with PID"):
        await sandbox_off.stop(99999)


@pytest.mark.asyncio
async def test_empty_command(sandbox_off: SandboxManager) -> None:
    """Starting with empty command raises SandboxError."""
    with pytest.raises(SandboxError, match="Empty command"):
        await sandbox_off.start("bad", [])


@pytest.mark.asyncio
async def test_list_running(sandbox_off: SandboxManager) -> None:
    """List returns all running sandbox entries."""
    mock_a = MagicMock()
    mock_a.pid = 12351
    mock_b = MagicMock()
    mock_b.pid = 12352

    with patch("subprocess.Popen", side_effect=[mock_a, mock_b]):
        await sandbox_off.start("server-a", ["true"])
        await sandbox_off.start("server-b", ["true"])

    running = await sandbox_off.list()
    assert len(running) == 2


@pytest.mark.asyncio
async def test_list_running_multiple_servers(sandbox_off: SandboxManager) -> None:
    """Multiple started processes appear in list()."""
    mock_a = MagicMock()
    mock_a.pid = 12351
    mock_b = MagicMock()
    mock_b.pid = 12352
