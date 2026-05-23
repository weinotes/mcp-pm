# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""
Sandbox manager — provides security isolation for MCP server execution.

Three isolation levels:
1. off:      no isolation, direct subprocess.Popen
2. subprocess: process-level isolation with resource limits and process groups
3. docker:   full container isolation via Docker

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import asyncio
import enum
import os
import resource
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp_pm.exceptions import SandboxError

# ── Sandbox root directory ──────────────────────────────────────────────
SANDBOX_ROOT: Path = Path.home() / ".mcp-pm" / "sandbox"

# Environment variables allowed through in subprocess mode
_ALLOWED_ENV_KEYS = frozenset({"PATH", "HOME"})

# Default timeout for health-check pings (seconds)
_HEALTH_PING_TIMEOUT = 5.0


# ── Level enumeration ───────────────────────────────────────────────────
class SandboxLevel(str, enum.Enum):
    OFF = "off"
    SUBPROCESS = "subprocess"
    DOCKER = "docker"
    FIRECRACKER = "firecracker"  # planned


# ── Internal book-keeping ───────────────────────────────────────────────
@dataclass
class _SandboxEntry:
    """Runtime state for a single sandboxed process."""

    server_name: str
    level: SandboxLevel
    pid: int
    command: list[str]

    # SUBPROCESS: asyncio subprocess handle
    process: asyncio.subprocess.Process | None = None

    # OFF: subprocess.Popen handle
    popen: Any = None  # subprocess.Popen

    # DOCKER: container id
    container_id: str | None = None

    started_at: float = field(default_factory=time.monotonic)


# ── Manager ─────────────────────────────────────────────────────────────
class SandboxManager:
    """Manages execution sandbox for MCP servers."""

    def __init__(self, level: SandboxLevel = SandboxLevel.SUBPROCESS) -> None:
        self.level = level
        self._sandboxes: dict[int, _SandboxEntry] = {}
        self._lock = asyncio.Lock()

    # ── start ───────────────────────────────────────────────────────────
    async def start(
        self,
        server_name: str,
        command: list[str],
        env: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> int:
        """Start a sandboxed process for an MCP server. Returns PID."""
        if not command:
            raise SandboxError("Empty command")

        level = self.level

        if level == SandboxLevel.OFF:
            pid = await self._start_off(server_name, command, env)
        elif level == SandboxLevel.SUBPROCESS:
            pid = await self._start_subprocess(server_name, command, env, timeout)
        elif level == SandboxLevel.DOCKER:
            pid = await self._start_docker(server_name, command, env)
        else:
            raise SandboxError(f"Unsupported sandbox level: {level}")

        return pid

    # ── stop ────────────────────────────────────────────────────────────
    async def stop(self, pid: int, timeout_seconds: int = 10) -> None:
        """Stop a sandboxed process gracefully, then force-kill."""
        async with self._lock:
            entry = self._sandboxes.get(pid)
            if entry is None:
                raise SandboxError(f"No sandbox with PID {pid}")

            try:
                if entry.level == SandboxLevel.OFF:
                    await self._stop_off(entry, timeout_seconds)
                elif entry.level == SandboxLevel.SUBPROCESS:
                    await self._stop_subprocess(entry, timeout_seconds)
                elif entry.level == SandboxLevel.DOCKER:
                    await self._stop_docker(entry, timeout_seconds)
            finally:
                self._sandboxes.pop(pid, None)

    # ── health ──────────────────────────────────────────────────────────
    async def health(self, pid: int) -> bool:
        """Check if a sandboxed process is healthy."""
        entry = self._sandboxes.get(pid)
        if entry is None:
            return False

        try:
            if entry.level == SandboxLevel.OFF:
                return self._health_off(entry)
            elif entry.level == SandboxLevel.SUBPROCESS:
                return await self._health_subprocess(entry)
            elif entry.level == SandboxLevel.DOCKER:
                return await self._health_docker(entry)
        except Exception:
            return False

        return False

    # ── list ────────────────────────────────────────────────────────────
    async def list(self) -> list[dict[str, Any]]:
        """List all running sandboxes."""
        async with self._lock:
            return [
                {
                    "server_name": e.server_name,
                    "pid": e.pid,
                    "level": e.level.value,
                    "command": e.command,
                    "started_at": e.started_at,
                    "uptime_seconds": time.monotonic() - e.started_at,
                    "container_id": e.container_id,
                }
                for e in self._sandboxes.values()
            ]

    # ── stats ───────────────────────────────────────────────────────────
    async def stats(self, pid: int) -> dict[str, Any]:
        """Return CPU / memory statistics for a sandboxed process."""
        entry = self._sandboxes.get(pid)
        if entry is None:
            raise SandboxError(f"No sandbox with PID {pid}")

        stats: dict[str, Any] = {
            "pid": pid,
            "server_name": entry.server_name,
            "level": entry.level.value,
            "uptime_seconds": time.monotonic() - entry.started_at,
        }

        try:
            proc_path = Path(f"/proc/{pid}")
            if proc_path.exists():
                # Basic /proc stats
                try:
                    stat_raw = (proc_path / "stat").read_text()
                    fields = stat_raw.split()
                    # field[13] = utime, field[14] = stime (clock ticks)
                    clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
                    utime = int(fields[13]) / clk_tck if len(fields) > 14 else 0.0
                    stime = int(fields[14]) / clk_tck if len(fields) > 15 else 0.0
                    stats["cpu_time_user"] = utime
                    stats["cpu_time_system"] = stime
                    stats["cpu_time_total"] = utime + stime
                except (IndexError, ValueError, OSError):
                    pass

                try:
                    status_text = (proc_path / "status").read_text()
                    for line in status_text.splitlines():
                        if line.startswith("VmRSS:"):
                            parts = line.split()
                            if len(parts) >= 2 and parts[1].isdigit():
                                stats["memory_rss_kb"] = int(parts[1])
                        elif line.startswith("VmSize:"):
                            parts = line.split()
                            if len(parts) >= 2 and parts[1].isdigit():
                                stats["memory_vsize_kb"] = int(parts[1])
                except OSError:
                    pass
        except Exception:
            pass

        return stats

    # ═══════════════════════════════════════════════════════════════════
    # Internal: OFF level
    # ═══════════════════════════════════════════════════════════════════
    async def _start_off(
        self, server_name: str, command: list[str], env: dict[str, str] | None
    ) -> int:
        import subprocess

        merged_env = {**os.environ, **(env or {})}
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged_env,
            )
        except FileNotFoundError:
            raise SandboxError(f"Command not found: {command[0]}")
        except OSError as exc:
            raise SandboxError(f"Failed to launch '{command[0]}': {exc}") from exc

        pid = proc.pid
        async with self._lock:
            self._sandboxes[pid] = _SandboxEntry(
                server_name=server_name,
                level=SandboxLevel.OFF,
                pid=pid,
                command=command,
                popen=proc,
            )
        return pid

    async def _stop_off(self, entry: _SandboxEntry, timeout_seconds: int) -> None:
        import subprocess

        proc: subprocess.Popen = entry.popen
        if proc.returncode is not None:
            return  # already dead

        try:
            os.kill(entry.pid, signal.SIGTERM)
            await asyncio.sleep(0)
            try:
                proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                os.kill(entry.pid, signal.SIGKILL)
                proc.wait(timeout=5)
        except ProcessLookupError:
            pass  # already gone

    def _health_off(self, entry: _SandboxEntry) -> bool:
        proc = entry.popen
        if proc is None or proc.returncode is not None:
            return False
        return True

    # ═══════════════════════════════════════════════════════════════════
    # Internal: SUBPROCESS level
    # ═══════════════════════════════════════════════════════════════════
    async def _start_subprocess(
        self,
        server_name: str,
        command: list[str],
        env: dict[str, str] | None,
        timeout: int,
    ) -> int:
        sandbox_dir = SANDBOX_ROOT / server_name
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Build clean environment
        clean_env: dict[str, str] = {}
        for key in _ALLOWED_ENV_KEYS:
            val = os.environ.get(key)
            if val is not None:
                clean_env[key] = val
        if env:
            clean_env.update(env)

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=clean_env,
                cwd=str(sandbox_dir),
                preexec_fn=_prepare_subprocess,
            )
        except FileNotFoundError:
            raise SandboxError(f"Command not found: {command[0]}")
        except OSError as exc:
            raise SandboxError(f"Failed to launch '{command[0]}': {exc}") from exc

        pid = process.pid
        if pid is None:
            raise SandboxError("Process started but PID is None")

        async with self._lock:
            self._sandboxes[pid] = _SandboxEntry(
                server_name=server_name,
                level=SandboxLevel.SUBPROCESS,
                pid=pid,
                command=command,
                process=process,
            )
        return pid

    async def _stop_subprocess(self, entry: _SandboxEntry, timeout_seconds: int) -> None:
        process = entry.process
        if process is None:
            return

        pid = entry.pid
        try:
            # Send SIGTERM to whole process group
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass

        try:
            await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                await process.wait()
            except Exception:
                pass

    async def _health_subprocess(self, entry: _SandboxEntry) -> bool:
        process = entry.process
        if process is None:
            return False
        if process.returncode is not None:
            return False

        # Ping-style timeout check: the process must be responsive
        try:
            await asyncio.wait_for(
                asyncio.sleep(0), timeout=_HEALTH_PING_TIMEOUT
            )
        except asyncio.TimeoutError:
            return False

        return True

    # ═══════════════════════════════════════════════════════════════════
    # Internal: DOCKER level
    # ═══════════════════════════════════════════════════════════════════
    async def _start_docker(
        self, server_name: str, command: list[str], env: dict[str, str] | None
    ) -> int:
        docker_args = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--name", f"mcp-pm-{server_name}",
        ]

        # Mount config directory
        config_dir = Path.home() / ".mcp-pm"
        if config_dir.exists():
            docker_args.extend(["-v", f"{config_dir}:/root/.mcp-pm"])

        # Pass environment variables
        if env:
            for key, val in env.items():
                docker_args.extend(["-e", f"{key}={val}"])

        docker_args.extend(command)

        try:
            process = await asyncio.create_subprocess_exec(
                *docker_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise SandboxError("Docker not found — is it installed?")
        except OSError as exc:
            raise SandboxError(f"Failed to run docker: {exc}") from exc

        pid = process.pid
        if pid is None:
            raise SandboxError("Docker process started but PID is None")

        # Record with placeholder container_id — we derive it from the name
        async with self._lock:
            self._sandboxes[pid] = _SandboxEntry(
                server_name=server_name,
                level=SandboxLevel.DOCKER,
                pid=pid,
                command=command,
                process=process,
                container_id=f"mcp-pm-{server_name}",
            )
        return pid

    async def _stop_docker(self, entry: _SandboxEntry, timeout_seconds: int) -> None:
        container_id = entry.container_id or f"mcp-pm-{entry.server_name}"
        try:
            stop_proc = await asyncio.create_subprocess_exec(
                "docker", "stop", "-t", str(timeout_seconds), container_id,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await stop_proc.wait()
        except FileNotFoundError:
            pass  # docker not found
        except OSError:
            pass

    async def _health_docker(self, entry: _SandboxEntry) -> bool:
        container_id = entry.container_id or f"mcp-pm-{entry.server_name}"
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect",
                "--format={{.State.Running}}",
                container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout_bytes, _ = await proc.communicate()
            return proc.returncode == 0 and stdout_bytes.decode().strip() == "true"
        except Exception:
            return False


# ── Helper: preexec for subprocess isolation ────────────────────────────
def _prepare_subprocess() -> None:
    """Run in forked child before exec.

    - Create a new process group (setsid)
    - Set resource limits (RLIMIT_AS for virtual memory)
    """
    try:
        os.setsid()
    except PermissionError:
        pass

    try:
        # Limit virtual memory to 1 GB
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        limit = 1024 * 1024 * 1024  # 1 GB
        resource.setrlimit(
            resource.RLIMIT_AS,
            (min(soft, limit) if soft > 0 else limit, hard),
        )
    except (ValueError, resource.error):
        pass
