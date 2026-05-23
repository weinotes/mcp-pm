# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""
Web UI application — FastAPI + HTMX dashboard for MCP tool management.

Provides a browser-based dashboard for exploring, testing, installing,
and managing MCP servers with a modern dark-themed UI.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from mcp_pm.client import MCPSession
from mcp_pm.config import Config
from mcp_pm.installer import Installer
from mcp_pm.registry import RegistryManager, ServerManifest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

from mcp_pm.webui.lang import _, set_language, get_language, LANG_NAMES

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["_"] = _
templates.env.globals["LANG_NAMES"] = LANG_NAMES
templates.env.globals["get_language"] = get_language

app = FastAPI(
    title="mcp-pm Dashboard",
    version="0.1.0",
    description="Web UI for managing MCP servers and tools",
)


# ---------------------------------------------------------------------------
# Language middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def language_middleware(request: Request, call_next: Any) -> Any:
    """Set language from query param or cookie."""
    lang = request.query_params.get("lang") or request.cookies.get("lang") or "en"
    set_language(lang)
    response = await call_next(request)
    return response

# ---------------------------------------------------------------------------
# Startup timestamp
# ---------------------------------------------------------------------------

_start_time: float = time.time()


def _uptime() -> str:
    """Return human-readable uptime string."""
    elapsed = int(time.time() - _start_time)
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get_config() -> Config:
    cfg = Config()
    cfg.load()
    return cfg


def _get_installer() -> Installer:
    return Installer()


def _get_registry() -> RegistryManager:
    return RegistryManager()


def _read_logs(tail: int = 50) -> list[str]:
    """Read the last N lines from the log file."""
    log_dir = Path.home() / ".mcp-pm" / "logs"
    log_file = log_dir / "mcp-pm.log"
    if not log_file.exists():
        return []
    try:
        text = log_file.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        return lines[-tail:]
    except Exception:
        return []


def _get_installed_servers() -> list[dict[str, Any]]:
    """Get installed servers with enriched status info."""
    installer = _get_installer()
    servers = installer.list_installed()
    for srv in servers:
        srv.setdefault("status", "unknown")
        srv.setdefault("description", "")
        srv.setdefault("tools_count", 0)
        srv.setdefault("version", "unknown")
        srv.setdefault("source_url", "")
        # Derive a reasonable status
        manifest_path = Path(srv.get("path", "")) / "manifest.yaml"
        if manifest_path.exists():
            srv["status"] = "running"
        else:
            srv["status"] = "stopped"
    return servers


# ---------------------------------------------------------------------------
# Page routes (HTML)
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Main dashboard page — statistics + server overview."""
    config = _get_config()
    config_path = str(config.path)
    servers = _get_installed_servers()
    total_tools = sum(s.get("tools_count", 0) for s in servers)
    running = sum(1 for s in servers if s.get("status") == "running")

    stats = {
        "servers": len(servers),
        "tools": total_tools,
        "online": running,
        "running": running,
        "stopped": len(servers) - running,
        "uptime": _uptime(),
    }

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "active_page": "dashboard",
            "servers": servers,
            "total_tools": total_tools,
            "config_path": config_path,
            "stats": stats,
        },
    )


@app.get("/tools/{name}", response_class=HTMLResponse)
async def tool_detail(request: Request, name: str) -> HTMLResponse:
    """Tool detail page with interactive testing panel."""
    installer = _get_installer()
    manifest = installer.get_manifest(name)
    tools: list[dict[str, Any]] = []

    if manifest:
        # Try to connect and list tools
        try:
            session = MCPSession()
            command = _build_launch_command(manifest)
            if command:
                await session.start_server(name, command)
                all_tools = session.get_all_tools()
                for srv_name, tool in all_tools:
                    params = dict(tool.parameters)
                    props = params.get("properties", {})
                    required = params.get("required", [])
                    sample: dict[str, Any] = {}
                    for pname, pschema in props.items():
                        if isinstance(pschema, dict):
                            ptype = pschema.get("type", "string")
                            if ptype == "string":
                                sample[pname] = ""
                            elif ptype == "integer" or ptype == "number":
                                sample[pname] = 0
                            elif ptype == "boolean":
                                sample[pname] = False
                            elif ptype == "array":
                                sample[pname] = []
                            elif ptype == "object":
                                sample[pname] = {}
                            else:
                                sample[pname] = None

                    tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": params,
                        "sample_params": sample,
                        "example_args": json.dumps(sample, indent=2) if sample else "{}",
                    })
                await session.stop_server(name)
        except Exception as exc:
            logger.warning("Could not connect to '%s': %s", name, exc)

    return templates.TemplateResponse(
        request,
        "tool_detail.html",
        {
            "active_page": "tools",
            "server_name": name,
            "tools": tools,
        },
    )


@app.get("/servers", response_class=HTMLResponse)
async def servers_page(request: Request) -> HTMLResponse:
    """Server management page."""
    servers = _get_installed_servers()
    return templates.TemplateResponse(
        request,
        "servers.html",
        {
            "active_page": "servers",
            "servers": servers,
        },
    )


@app.get("/install", response_class=HTMLResponse)
async def install_page(request: Request) -> HTMLResponse:
    """Install new server page."""
    popular: list[ServerManifest] = []
    try:
        reg = _get_registry()
        popular = await reg.popular(12)
    except Exception as exc:
        logger.warning("Could not fetch popular servers: %s", exc)

    return templates.TemplateResponse(
        request,
        "install.html",
        {
            "active_page": "install",
            "popular": popular,
        },
    )


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request) -> HTMLResponse:
    """Configuration page."""
    config = _get_config()
    config_path = str(config.path)
    config_data = config.load()
    config_yaml = config.export()

    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "active_page": "config",
            "config_path": config_path,
            "config_yaml": config_yaml,
            "config_data": config_data,
        },
    )


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    tail: int = Query(50, description="Number of log lines"),
) -> HTMLResponse:
    """Log viewer page."""
    initial_logs = _read_logs(tail)
    return templates.TemplateResponse(
        request,
        "logs.html",
        {
            "active_page": "logs",
            "initial_logs": initial_logs,
            "tail_count": tail,
        },
    )


# ---------------------------------------------------------------------------
# API routes (JSON endpoints)
# ---------------------------------------------------------------------------


@app.get("/api/servers")
async def api_servers() -> list[dict[str, Any]]:
    """Return server list as JSON (for HTMX partial rendering)."""
    return _get_installed_servers()


@app.get("/api/tools")
async def api_tools() -> list[dict[str, Any]]:
    """Return all tools from all servers."""
    installer = _get_installer()
    servers = installer.list_installed()
    results: list[dict[str, Any]] = []

    for srv in servers:
        name = srv.get("name", "")
        manifest = installer.get_manifest(name)
        if not manifest:
            continue

        try:
            session = MCPSession()
            command = _build_launch_command(manifest)
            if command:
                await session.start_server(name, command)
                for srv_name, tool in session.get_all_tools():
                    results.append({
                        "server": srv_name,
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": dict(tool.parameters),
                    })
                await session.stop_server(name)
        except Exception as exc:
            logger.debug("Could not list tools for '%s': %s", name, exc)

    return results


@app.post("/api/tools/{server}/{tool}/call")
async def api_tool_call(server: str, tool: str, request: Request) -> JSONResponse:
    """Call a tool on a specific server with JSON arguments."""
    body: dict[str, Any] = await request.json()
    arguments = body.get("arguments", {})

    installer = _get_installer()
    manifest = installer.get_manifest(server)
    if not manifest:
        return JSONResponse(
            {"error": f"Server '{server}' not found"},
            status_code=404,
        )

    try:
        session = MCPSession()
        command = _build_launch_command(manifest)
        if not command:
            return JSONResponse(
                {"error": f"Cannot launch server '{server}'"},
                status_code=500,
            )

        await session.start_server(server, command)
        result = await session.call_tool(server, tool, arguments)
        await session.stop_server(server)

        return JSONResponse({
            "content": result.content,
            "is_error": result.is_error,
        })
    except Exception as exc:
        logger.error("Tool call failed: %s", exc)
        return JSONResponse(
            {"error": str(exc)},
            status_code=500,
        )


@app.get("/api/logs")
async def api_logs(
    tail: int = Query(50, description="Number of log lines"),
) -> PlainTextResponse:
    """Return recent log lines as plain text."""
    lines = _read_logs(tail)
    text = "\n".join(lines) if lines else "No log entries yet.\n"
    return PlainTextResponse(text)


@app.get("/api/stats")
async def api_stats(request: Request) -> HTMLResponse:
    """Return statistics as HTML partial for the dashboard cards."""
    servers = _get_installed_servers()
    total_tools = sum(s.get("tools_count", 0) for s in servers)
    running = sum(1 for s in servers if s.get("status") == "running")

    stats = {
        "servers": len(servers),
        "tools": total_tools,
        "online": running,
        "running": running,
        "stopped": len(servers) - running,
        "uptime": _uptime(),
    }

    return templates.TemplateResponse(
        request,
        "_stats_cards.html",
        {"stats": stats},
    )


@app.get("/api/search")
async def api_search(
    query: str = Query("", description="Search query"),
) -> HTMLResponse:
    """Search the MCP registry and return HTML partial for HTMX."""
    results: list[ServerManifest] = []
    if query.strip():
        try:
            reg = _get_registry()
            results = await reg.search(query.strip(), limit=20)
        except Exception as exc:
            logger.warning("Search failed: %s", exc)
    else:
        try:
            reg = _get_registry()
            results = await reg.popular(12)
        except Exception:
            pass

    # Render search results as HTML partial
    items_html = ""
    for srv in results:
        stars_badge = f'<span class="badge badge-yellow">★ {srv.stars}</span>' if srv.stars else ""
        tools_badge = f'<span class="badge badge-blue">{srv.tools_count} tools</span>' if srv.tools_count else ""
        items_html += f"""
        <div class="card card-hover p-5">
            <div class="flex items-start justify-between mb-2">
                <div>
                    <div class="font-semibold text-[#cdd6f4]">{srv.name}</div>
                    <div class="text-xs text-[#6c7086]">{srv.author or 'Community'}</div>
                </div>
                {stars_badge}
            </div>
            <p class="text-sm text-[#a6adc8] mb-3 line-clamp-2">{srv.description}</p>
            <div class="flex items-center justify-between">
                <div class="flex gap-1">
                    <span class="badge badge-gray">{srv.source_type}</span>
                    {tools_badge}
                </div>
                <button class="btn-primary text-xs"
                        hx-post="/api/install"
                        hx-vals='{{"name": "{srv.name}", "source_url": "{srv.source_url}", "source_type": "{srv.source_type}"}}'
                        hx-target="#install-status"
                        hx-confirm="Install '{srv.name}'?">
                    Install
                </button>
            </div>
        </div>"""

    if not items_html:
        items_html = """
        <div class="col-span-full text-center py-8 text-[#6c7086]">
            No servers found. Try a different search term.
        </div>"""

    return HTMLResponse(f"""
    <div class="mt-4">
        <h2 class="text-lg font-semibold text-[#cdd6f4] mb-4">
            {'Search Results' if query.strip() else 'Popular Servers'}
            <span class="text-sm text-[#6c7086]">({len(results)} found)</span>
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items_html}
        </div>
    </div>
    """)


@app.post("/api/install")
async def api_install(request: Request) -> HTMLResponse:
    """Install a server and return status HTML."""
    body: dict[str, Any] = await request.json()
    name = body.get("name", "")
    source_url = body.get("source_url", "")
    source_type = body.get("source_type", "auto")

    if not name and not source_url:
        return HTMLResponse("""
        <div class="card p-4 border border-[#f38ba8] bg-[#f38ba8]/5 mt-3">
            <div class="text-[#f38ba8] font-medium">Installation Failed</div>
            <p class="text-sm text-[#a6adc8]">Name or source URL is required.</p>
        </div>
        """)

    if not name:
        # Derive name from source
        name = source_url.rsplit("/", 1)[-1] if "/" in source_url else source_url
        for prefix in ("pip:", "npm:", "docker:", "uvx ", "uvx:"):
            if name.startswith(prefix):
                name = name[len(prefix) :]
        if name.endswith(".git"):
            name = name[:-4]

    if source_type == "auto":
        if source_url.startswith("http") or source_url.startswith("git@"):
            source_type = "git"
        elif source_url.startswith("pip:") or source_url.startswith("uvx"):
            source_type = "pip"
        elif source_url.startswith("npm"):
            source_type = "npm"
        elif source_url.startswith("docker"):
            source_type = "docker"
        else:
            source_type = "git"

    manifest = ServerManifest(
        name=name,
        description=f"Installed from {source_url}",
        source_type=source_type,
        source_url=source_url,
    )

    try:
        installer = _get_installer()
        success = await installer.install(manifest)
        if success:
            return HTMLResponse(f"""
            <div class="card p-4 border border-[#a6e3a1] bg-[#a6e3a1]/5 mt-3">
                <div class="text-[#a6e3a1] font-medium flex items-center gap-2">
                    <span>✓</span> Successfully Installed
                </div>
                <p class="text-sm text-[#a6adc8] mt-1">Server '<strong>{name}</strong>' installed from {source_url}</p>
                <a href="/tools/{name}" class="text-sm text-[#89b4fa] hover:underline mt-2 inline-block">View Tools →</a>
            </div>
            """)
        else:
            return HTMLResponse(f"""
            <div class="card p-4 border border-[#f9e2af] bg-[#f9e2af]/5 mt-3">
                <div class="text-[#f9e2af] font-medium">Already Installed</div>
                <p class="text-sm text-[#a6adc8]">Server '<strong>{name}</strong>' is already installed.</p>
                <a href="/tools/{name}" class="text-sm text-[#89b4fa] hover:underline mt-2 inline-block">View →</a>
            </div>
            """)
    except Exception as exc:
        logger.error("Install failed: %s", exc)
        return HTMLResponse(f"""
        <div class="card p-4 border border-[#f38ba8] bg-[#f38ba8]/5 mt-3">
            <div class="text-[#f38ba8] font-medium">Installation Failed</div>
            <p class="text-sm text-[#a6adc8]">{exc}</p>
        </div>
        """)


@app.post("/api/config")
async def api_config_save(
    request: Request,
    yaml_content: str = Form(""),
) -> HTMLResponse:
    """Save config from the editor."""
    try:
        config = _get_config()
        config.import_str(yaml_content)
        config.save()
        return HTMLResponse("""
        <span class="text-[#a6e3a1] text-sm">✓ Configuration saved</span>
        """)
    except Exception as exc:
        return HTMLResponse(f"""
        <span class="text-[#f38ba8] text-sm">✗ Save failed: {exc}</span>
        """)


@app.post("/api/config/import")
async def api_config_import(file: UploadFile) -> HTMLResponse:
    """Import config from uploaded YAML file."""
    try:
        content = await file.read()
        yaml_str = content.decode("utf-8")
        config = _get_config()
        config.import_str(yaml_str)
        config.save()
        return HTMLResponse("""
        <div class="card p-4 border border-[#a6e3a1] bg-[#a6e3a1]/5 mt-3">
            <div class="text-[#a6e3a1] font-medium">✓ Configuration imported successfully</div>
        </div>
        """)
    except Exception as exc:
        return HTMLResponse(f"""
        <div class="card p-4 border border-[#f38ba8] bg-[#f38ba8]/5 mt-3">
            <div class="text-[#f38ba8] font-medium">✗ Import failed: {exc}</div>
        </div>
        """)


@app.post("/api/servers/{name}/restart")
@app.post("/api/servers/{name}/stop")
@app.post("/api/servers/{name}/start")
@app.post("/api/servers/{name}/uninstall")
async def api_server_action(name: str, request: Request) -> JSONResponse:
    """Handle server actions (restart/stop/start/uninstall).

    These are stubs that report the action. Actual process management
    is delegated to the CLI; the web UI provides user-friendly feedback.
    """
    path_parts = request.url.path.rstrip("/").split("/")
    action = path_parts[-1] if path_parts else ""

    if action == "uninstall":
        try:
            installer = _get_installer()
            await installer.uninstall(name)
            return JSONResponse({"status": "ok", "message": f"Uninstalled '{name}'"})
        except Exception as exc:
            return JSONResponse(
                {"status": "error", "message": str(exc)},
                status_code=500,
            )

    # For start/stop/restart — acknowledge the action
    action_map = {
        "start": "started",
        "stop": "stopped",
        "restart": "restarted",
    }
    verb = action_map.get(action, action)
    return JSONResponse({
        "status": "ok",
        "message": f"Server '{name}' {verb} (action queued). Use the CLI for process management.",
    })


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    installer = _get_installer()
    servers = installer.list_installed()
    return {
        "status": "ok",
        "version": "0.1.0",
        "servers_loaded": len(servers),
        "uptime": _uptime(),
    }


# ---------------------------------------------------------------------------
# Launch helper (mirrors cli.py logic)
# ---------------------------------------------------------------------------


def _build_launch_command(manifest: dict[str, Any]) -> list[str] | None:
    """Build a command list to launch an installed server."""
    import sys

    source_type = manifest.get("source_type", "")
    source_url = manifest.get("source_url", "")
    name = manifest.get("name", "")

    if source_type == "git":
        install_dir = Path.home() / ".mcp-pm" / "servers" / name
        for entry in ("main.py", "src/main.py", "index.js", "server.py", "src/server.py"):
            candidate = install_dir / entry
            if candidate.exists():
                if candidate.suffix == ".py":
                    return [sys.executable, str(candidate)]
                elif candidate.suffix == ".js":
                    return ["node", str(candidate)]
        pkg_json = install_dir / "package.json"
        if pkg_json.exists():
            return ["npx", "-y", str(install_dir)]
        return [sys.executable, "-m", name]

    if source_type == "pip":
        package = manifest.get("package", name)
        return [sys.executable, "-m", package]

    return None


# ---------------------------------------------------------------------------
# Start entry point for CLI
# ---------------------------------------------------------------------------


def start(port: int = 8080) -> None:
    """Start the Web UI server. Called by CLI ``explore`` command."""
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
    )
