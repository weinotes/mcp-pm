# MCP-PM (Model Context Protocol Package Manager) — Architecture Design Document

- **Author**: Davey Wong `<wgwcko@gmail.com>`
- **Status**: Draft v0.1
- **Last Updated**: 2026-05-24
- **License**: MIT

---

## 1. Objective and Background

### 1.1 Background

Model Context Protocol (MCP) is an open protocol by Anthropic that standardizes how AI applications connect with external tools and data sources. As the MCP ecosystem rapidly expands — with 21K+ servers listed on MCP.so, 5.6K+ on Smithery, and an official GitHub MCP Registry — there is **no unified "brew-like" experience** for discovering, installing, managing, configuring, and running MCP servers.

Each server may be distributed as a Python package (pip), a Node.js package (npm), a Git repository, or a Docker image. Users currently must manually install dependencies, configure environment variables, and wire servers into their AI client's configuration. This friction limits the adoption of MCP for both developers and end-users.

### 1.2 Objective

Build **mcp-pm** — "Homebrew for MCP Servers" — a single CLI tool (and optional Web UI) that provides:

1. **Discovery**: Search a federated registry for MCP servers.
2. **Installation**: One-command install from any source (registry, git, npm, pip).
3. **Management**: List, update, remove, and inspect installed servers and their tools.
4. **Configuration**: Centralized configuration with export/import for client migration.
5. **Runtime**: Expose all installed MCP tools via an OpenAI-compatible API proxy.
6. **Safety**: Optional sandbox isolation for untrusted servers.

---

## 2. Goals and Non-Goals

### 2.1 Goals

| Goal | Priority | Description |
|------|----------|-------------|
| **Brew-like CLI** | P0 | `mcp install`, `mcp list`, `mcp search`, `mcp remove` — intuitive, minimal surprise |
| **Multi-source installation** | P0 | Install from registry, Git, npm, pip |
| **Centralized config** | P0 | Single `mcp.json` config file per user, with export/import |
| **Tool introspection** | P0 | List installed servers and their exposed tools/schemas |
| **OpenAI-compatible proxy** | P1 | `mcp serve :8080` exposes all tools as OpenAI function-calling API |
| **Web UI explorer** | P1 | `mcp explore` opens a browser-based tool tester |
| **Registry client** | P1 | Query and publish to a federated registry |
| **Sandbox isolation** | P2 | `mcp sandbox on/off` for running servers in isolated environments |

### 2.2 Non-Goals

- **MCP server runtime**: We do _not_ reimplement the MCP protocol server SDK. We consume servers that implement the MCP standard.
- **MCP registry hosting**: The initial version queries community registries (MCP.so, Smithery, GitHub) rather than hosting a first-party registry.
- **AI client**: mcp-pm is a tool runner and proxy, not an AI chat interface.
- **Docker orchestration**: No Kubernetes or Docker Compose support in v1. Docker usage is limited to running sandboxed servers.
- **Windows support**: v1 targets macOS and Linux. Windows support is tracked as a future milestone.

---

## 3. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │    CLI        │  │   Web UI     │  │  AI Client (e.g.    │  │
│  │  (Click/Rich) │  │ (FastAPI+    │  │  Claude Desktop)    │  │
│  │               │  │  HTMX)       │  │                      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
└─────────┼──────────────────┼─────────────────────┼──────────────┘
          │                  │                     │
          ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     mcp-pm Core (Python 3.11+)                   │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │  Registry  │  │  Installer │  │  Config    │  │ Sandbox  │  │
│  │  Client    │  │  Engine    │  │  Manager   │  │ Manager  │  │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └────┬─────┘  │
│        │               │               │               │        │
│        ▼               ▼               ▼               ▼        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              MCP Client (HTTP/SSE transport)            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │             Proxy Server (uvicorn + SSE)                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      External Systems                            │
│                                                                  │
│  ┌──────────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐  │
│  │ MCP.so       │  │ GitHub    │  │ npm      │  │ pip/PyPI  │  │
│  │ Registry API │  │ MCP Reg.  │  │ Registry │  │           │  │
│  └──────────────┘  └───────────┘  └──────────┘  └───────────┘  │
│                                                                  │
│  ┌──────────────┐  ┌───────────┐                                │
│  │  MCP Server  │  │  MCP      │                                │
│  │  Processes   │  │  Server ( │                                │
│  │  (subprocess)│  │  Docker)  │                                │
│  └──────────────┘  └───────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Architecture Principles

1. **Plugin-style server abstraction**: Each installed MCP server is represented by a `ServerEntry` with its source, version, capabilities, and runtime status.
2. **Layered isolation**: The installer layer is separated from runtime; the sandbox is an optional wrapper around the runtime.
3. **Configuration as code**: All state lives in `~/.mcp/config.json` and `~/.mcp/servers/<name>/`. The system is stateless w.r.t. the CLI process itself.
4. **Transport abstraction**: Currently supports stdio transport (spawning servers as subprocesses). HTTP/SSE transport support is planned.
5. **Single user, single machine**: v1 is a single-user local tool. Multi-user and remote-server modes are future concerns.

---

## 4. Core Component Design

### 4.1 CLI Module (`mcp_pm/cli/`)

**Purpose**: Provide the user-facing command interface using Click and Rich.

**Key classes**:

```
mcp_pm/cli/
├── __init__.py          # Click group definition
├── install.py           # `mcp install <server>` — multi-source install
├── list_.py             # `mcp list` — list installed servers + tools
├── search.py            # `mcp search <query>` — registry search
├── explore.py           # `mcp explore` — launch Web UI
├── serve.py             # `mcp serve :8080` — start proxy
├── config.py            # `mcp config export/import`
├── remove.py            # `mcp remove <server>`
├── sandbox.py           # `mcp sandbox on/off`
└── update.py            # `mcp update [server]`
```

**Design decisions**:
- Use Click's `@click.group()` for the top-level CLI, with nested groups where appropriate (e.g., `mcp config export`, `mcp config import`).
- Use Rich for all terminal output: tables (`list`), progress bars (`install`), panels (`search`).
- Each subcommand delegates to the corresponding core module, keeping CLI thin.
- Handle `KeyboardInterrupt` gracefully — kill spawned server processes on Ctrl+C.

### 4.2 Registry Client (`mcp_pm/registry/`)

**Purpose**: Query external MCP server indexes and provide a unified search/install interface.

**Key classes**:

| Class | Responsibility |
|-------|---------------|
| `RegistryClient` (ABC) | Abstract base class for all registry backends |
| `McpDotSoClient` | Queries MCP.so public API (21K+ servers) |
| `SmitheryClient` | Queries Smithery hosted platform API |
| `GitHubRegistryClient` | Queries GitHub MCP Registry |
| `CompositeRegistry` | Aggregates results from multiple backends with dedup |

**Flow for `mcp search`**:
1. `CompositeRegistry.search(query)` fans out to all registered backends.
2. Results are merged by server name/ID, ranked by relevance or popularity.
3. Return `list[ServerInfo]` with: name, description, source URL, install type, tags, popularity score.

**Flow for `mcp install`**:
1. If argument is a direct URL (`git+https://...`, `npm:pkg`, `pip:pkg`), install directly.
2. Otherwise, search registries for the server by name.
3. Resolve the best installation method based on server metadata.
4. Return `InstallationPlan` with install type, source, version, and config defaults.

### 4.3 Installer Engine (`mcp_pm/installer/`)

**Purpose**: Execute the installation plan — download, resolve dependencies, and register the server locally.

**Key classes**:

| Class | Responsibility |
|-------|---------------|
| `InstallerEngine` | Orchestrator — resolves plans, delegates to specific installers |
| `GitInstaller` | `git clone` + optional build step (e.g., `npm install`, `pip install`) |
| `NpmInstaller` | `npm install -g <pkg>` or local install |
| `PipInstaller` | `pip install <pkg>` in a managed virtual environment |
| `DockerInstaller` | `docker pull` and create a run configuration |

**Installation lifecycle**:
```
InstallPlan
  → Engine.lock()          # Acquire lock on ~/.mcp/lock
  → Engine.download()      # Fetch source
  → Engine.resolve_deps()  # Resolve dependencies (language-specific)
  → Engine.build()         # Build if needed (e.g., TypeScript → JS)
  → Engine.register()      # Write server manifest to ~/.mcp/servers/<name>/
  → Engine.unlock()
```

**Server Manifest (`~/.mcp/servers/<name>/manifest.json`)**:
```json
{
  "name": "server-name",
  "version": "1.2.3",
  "source": {
    "type": "npm",
    "url": "npm:@org/server-name",
    "ref": "1.2.3"
  },
  "runtime": {
    "command": "node",
    "args": ["path/to/server/build/index.js"],
    "env": {}
  },
  "tools": [],
  "installed_at": "2026-05-24T00:35:00Z",
  "sandbox": false
}
```

### 4.4 MCP Client (`mcp_pm/client/`)

**Purpose**: Communicate with MCP servers using the Model Context Protocol via stdio transport.

**Key classes**:

| Class | Responsibility |
|-------|---------------|
| `McpClient` | Low-level JSON-RPC over stdio: `send_request()`, `receive_response()` |
| `SessionManager` | Manages lifecycle of server processes — start, stop, restart, health check |
| `ToolRegistry` | Caches `tools/list` results per server for fast introspection |

**Protocol flow** (per server process):
1. Spawn subprocess: `Popen([command, ...args], env=env)`.
2. Send `initialize` request (MCP handshake).
3. Receive `initialized` response with server capabilities.
4. Send `tools/list` to discover available tools.
5. Route subsequent tool call requests to the appropriate server.
6. On shutdown, send `shutdown` notification, then `SIGTERM`.

**Design decisions**:
- Use `asyncio.subprocess` for non-blocking process management.
- Implement a JSON-RPC dispatcher with request/response correlation via `id` field.
- Handle server crashes gracefully — auto-restart with exponential backoff (up to 3 retries).
- Stream large responses via SSE when using HTTP transport.

### 4.5 Proxy Server (`mcp_pm/proxy/`)

**Purpose**: Expose all installed MCP tools as a single OpenAI-compatible API endpoint.

**Endpoints**:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/models` | List all tools as "models" |
| `POST` | `/v1/chat/completions` | Accept OpenAI-format request, route tool calls |
| `GET` | `/health` | Health check |

**Architecture**:
```
                                               ┌──────────────┐
Post /v1/chat/completions                      │ MCP Server A │
  ┌──────────┐     ┌──────────────┐            │ (subprocess) │
  │ OpenAI   │────▶│  Dispatcher  │───────────▶│              │
  │ Request  │     │  (tool_call  │            └──────────────┘
  │ Parser   │     │   router)    │            ┌──────────────┐
  └──────────┘     │              │───────────▶│ MCP Server B │
                   │              │            │ (subprocess) │
                   └──────────────┘            └──────────────┘
```

- Powered by **uvicorn** + **Starlette** for minimal overhead.
- The dispatcher parses `tools` from the OpenAI message, maps to the correct MCP server via `ToolRegistry`, calls the server, and returns a formatted response.
- Supports streaming (SSE) for chat completions when `stream=True`.
- Handles tool call batching: multiple tool calls in one response are dispatched concurrently.

### 4.6 Web UI (`mcp_pm/web/`)

**Purpose**: Provide a browser-based GUI for exploring and testing installed MCP tools.

**Tech stack**: FastAPI (backend) + HTMX + Jinja2 templates (frontend).

**Pages**:
| Route | Description |
|-------|-------------|
| `/` | Dashboard — list all servers and tool counts |
| `/server/<name>` | Server detail — all tools with their JSON schemas |
| `/tool/<server>/<tool>` | Interactive tool tester — fill params, call, see results |
| `/logs` | Real-time logs from server processes |

**Design decisions**:
- HTMX for interactivity: no JavaScript build step, minimal frontend complexity.
- Server-side rendering via Jinja2 templates.
- Real-time log streaming via Server-Sent Events (SSE).
- API routes (`/api/servers`, `/api/tools/<server>/<tool>/execute`) are shared between Web UI and CLI.

### 4.7 Sandbox Manager (`mcp_pm/sandbox/`)

**Purpose**: Provide optional security isolation for running untrusted MCP servers.

**Implementation strategies** (in order of preference):

| Strategy | Sandbox Level | Requirement |
|----------|---------------|-------------|
| **Subprocess** | None (default) | No extra requirements |
| **Docker** | Container-level | Docker daemon |
| **Firecracker/NsJail** | Micro VM / chroot | Linux + root or nsjail binary |

**Sandbox modes**:
- `off` (default): Run servers as direct subprocesses.
- `on --engine=docker`: Each server runs in a dedicated Docker container with:
  - Read-only filesystem (except temp dirs)
  - Network restricted (default deny, allow only needed endpoints)
  - Resource limits (CPU, memory) via Docker cgroups
  - Ephemeral containers destroyed on shutdown

**Configuration per server**:
```json
{
  "sandbox": {
    "enabled": true,
    "engine": "docker",
    "image": "python:3.11-slim",
    "resource_limits": {
      "memory": "512m",
      "cpu": "0.5"
    },
    "network_access": ["api.github.com"]
  }
}
```

---

## 5. Data Structures

### 5.1 Configuration (`~/.mcp/config.json`)

```json
{
  "version": 1,
  "registries": {
    "mcp_so": { "enabled": true },
    "smithery": { "enabled": true },
    "github": { "enabled": false }
  },
  "sandbox": {
    "default_engine": "subprocess",
    "docker": {
      "default_image": "python:3.11-slim",
      "memory_limit": "512m",
      "cpu_limit": 0.5
    }
  },
  "proxy": {
    "host": "127.0.0.1",
    "port": 8080,
    "api_key": null
  },
  "web": {
    "host": "127.0.0.1",
    "port": 3000
  }
}
```

### 5.2 Server Manifest (`~/.mcp/servers/<name>/manifest.json`)

Described in §4.3. The `tools` field is populated lazily after the first `tools/list` response from the server.

### 5.3 Registry Index Entry

```python
@dataclass
class ServerInfo:
    name: str
    description: str
    version: str
    source_type: Literal["npm", "pip", "git", "docker", "registry"]
    source_url: str
    install_guide: str | None       # Optional install instructions
    tags: list[str]
    homepage: str | None
    license: str | None
    popularity_score: float         # 0.0–1.0 normalized
```

### 5.4 Installation Plan

```python
@dataclass
class InstallPlan:
    server: ServerInfo
    install_type: Literal["git", "npm", "pip", "docker"]
    source_ref: str                 # Version tag, commit hash, or package version
    runtime_command: str
    runtime_args: list[str]
    default_env: dict[str, str]
    post_install_hooks: list[str]   # Scripts to run after install
```

---

## 6. API Design

### 6.1 CLI Commands

```
mcp install <server> [--from git|npm|pip] [--version <ver>] [--sandbox]
    安装MCP服务器。支持从注册中心、Git、npm或pip安装。
    如果不指定源，自动从注册中心查找最佳安装方式。

mcp list [--tools] [--json]
    列出所有已安装的MCP服务器。
    --tools   同时列出每个服务器提供的所有工具
    --json    以JSON格式输出（便于脚本处理）

mcp search <query> [--limit N] [--source mcp.so|smithery|github]
    从注册中心搜索MCP服务器。

mcp explore
    打开Web UI可视化浏览和测试所有工具。

mcp serve [<host>:<port>] [--api-key <key>] [--stream]
    将所有已安装的MCP工具暴露为OpenAI兼容API。
    默认端口 :8080

mcp config export [--path <file>]
    导出所有配置为JSON文件，用于跨客户端迁移。

mcp config import <file>
    从JSON文件导入配置。

mcp config set <key> <value>
    设置配置项（如sandbox.docker.memory_limit=1g）。

mcp remove <server>
    卸载MCP服务器并删除本地数据。

mcp update [<server>]
    更新所有或指定服务器到最新版本。

mcp sandbox on [--engine docker] [--all]
    对所有新安装的服务器启用沙箱隔离。

mcp sandbox off
    禁用沙箱隔离。

mcp info <server>
    显示服务器的详细信息，包括版本、源、环境变量和工具列表。
```

### 6.2 Internal Python API

```python
# Registry
class RegistryClient(ABC):
    async def search(self, query: str, limit: int = 20) -> list[ServerInfo]: ...
    async def resolve(self, name: str) -> ServerInfo | None: ...

# Installer
class InstallerEngine:
    async def plan(self, server: str | ServerInfo) -> InstallPlan: ...
    async def execute(self, plan: InstallPlan) -> ServerManifest: ...
    async def remove(self, name: str) -> None: ...
    async def update(self, name: str | None = None) -> list[ServerManifest]: ...

# Config
class ConfigManager:
    def load() -> Config: ...
    def save(config: Config) -> None: ...
    def export(path: str) -> None: ...
    def import_(path: str) -> Config: ...

# MCP Client
class SessionManager:
    async def start_server(self, manifest: ServerManifest) -> ToolRegistry: ...
    async def stop_server(self, name: str) -> None: ...
    async def call_tool(self, server: str, tool: str, args: dict) -> dict: ...

# Proxy
class ProxyServer:
    async def start(self, host: str, port: int) -> None: ...
    async def shutdown(self) -> None: ...

# Web UI
class WebApp:
    async def start(self, host: str, port: int) -> None: ...
    async def shutdown(self) -> None: ...

# Sandbox
class SandboxManager:
    async def create_env(self, manifest: ServerManifest) -> SandboxEnv: ...
    async def destroy_env(self, name: str) -> None: ...
```

### 6.3 External API (OpenAI-Compatible Proxy)

**`POST /v1/chat/completions`**

Request:
```json
{
  "model": "any",
  "messages": [
    {"role": "user", "content": "What's the weather in Tokyo?"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "weather__get_forecast",
        "description": "Get weather forecast for a city",
        "parameters": { ... }
      }
    }
  ],
  "stream": false
}
```

Response:
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "call_xxx",
        "type": "function",
        "function": {
          "name": "weather__get_forecast",
          "arguments": "{\"city\": \"Tokyo\"}"
        }
      }]
    }
  }]
}
```

**Tool naming convention**: `<server_name>__<tool_name>` to avoid naming collisions across servers.

---

## 7. Security Considerations

### 7.1 Threat Model

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Malicious MCP server reads local files | **High** | Sandbox mode (Docker/chroot); user warning on `mcp install` from untrusted source |
| Server sends data to external URL | **High** | Network deny-by-default in sandbox mode; proxy logs all outbound tool calls |
| Dependency confusion (typocat install) | **Medium** | Verify source integrity; cache known-good hashes; warn on name similarity |
| Arbitrary code execution via `npm install` | **High** | Run installs in temp dir with limited scope; sandbox the install process itself |
| Config file tampering | **Low** | Config files are user-owned; no elevated privileges needed |
| API proxy exposed on public network | **Medium** | Default bind to `127.0.0.1`; `--api-key` authentication; warn if binding to `0.0.0.0` |

### 7.2 Security Design Decisions

1. **Default to subprocess, opt-in to sandbox**: Sandbox adds friction (Docker dependency, startup latency). We default to direct subprocess with a clear security warning on first install.
2. **No root required**: All state lives under `~/.mcp/`. No `sudo` needed.
3. **API key authentication**: The proxy server can require an API key (sent as `Authorization: Bearer <key>`), matching the OpenAI API convention.
4. **Install-time validation**: Before executing an install plan, the engine validates:
   - Source URL matches the claimed source type (e.g., `npm:` prefix for npm packages)
   - No dangerous `postinstall` scripts in npm packages (if detectable)
   - Server manifest contains explicit `runtime.command` and `runtime.args` (no free-form execution)
5. **Audit log**: All tool invocations are logged to `~/.mcp/audit.log` with timestamp, server name, tool name, and caller IP (for proxy mode).

### 7.3 Secret Management

- Environment variables containing secrets (API keys, tokens) are stored in `~/.mcp/secrets/` with file permissions `600`.
- Secrets can be set via `mcp config set server.<name>.env.API_KEY=<value>` and are automatically moved to the secrets directory.
- The proxy server never exposes secrets in its responses.

---

## 8. Alternative Analysis

### 8.1 Why not extend existing tools?

| Alternative | Analysis | Decision |
|-------------|----------|----------|
| **Extend MCP.so** | MCP.so is a directory, not a CLI. Extending would require their cooperation. They lack runtime management. | Rejected |
| **Use `npx` / `pipx` directly** | These are package runners, not MCP-aware. No config management, no registry search, no proxy. | Rejected |
| **Build on Claude Desktop config** | Claude Desktop already has a JSON config for MCP servers. But this is client-specific, doesn't work with other AI clients, and has no CLI. | Partial integration: mcp-pm can export to Claude Desktop format |
| **Shell scripts + Makefile** | Too brittle; no dependency management, parallel execution, or sandboxing. | Rejected |
| **Go rewrite** | Better startup time, but Python ecosystem is a better fit for pip/npm integration and Rich-based CLI. | Keep Python; consider Rust/Go for performance-critical sandbox layer |

### 8.2 Why Python vs TypeScript/Go?

| Factor | Python | TypeScript | Go |
|--------|--------|------------|-----|
| Ecosystem for subprocess mgmt | ✅ `asyncio.subprocess` | ✅ `child_process` | ✅ `os/exec` |
| Rich CLI libraries | ✅ Click + Rich | ❌ Inquirer (limited) | ✅ Cobra + Bubble Tea |
| MCP ecosystem overlap | ✅ Large | ✅ Largest | ❌ Small |
| Web UI (FastAPI+HTMX) | ✅ FastAPI | ✅ Next.js | ❌ Gin + templ (OK) |
| Install speed | ⚠️ Slower startup | ❌ Node.js needed | ✅ Fast binary |
| Cross-platform | ✅ | ✅ | ✅ |

**Decision**: Python 3.11+ is the right pragmatic choice for a CLI tool that heavily integrates with `pip`, `npm` (via subprocess), and benefits from Click/Rich/FastAPI. If startup time becomes a concern, we can compile with Nuitka or migrate the sandbox layer to Go.

### 8.3 Configuration Storage: JSON vs YAML vs TOML

| Format | Pro | Con |
|--------|-----|-----|
| **JSON** | Ubiquitous, `json` in stdlib, easy to parse in any language | No comments; slightly verbose |
| **YAML** | Comments supported, cleaner for humans | Security concerns (arbitrary code loading in some parsers) |
| **TOML** | Clean, typed, `tomllib` in Python 3.11+ | Less universal than JSON |

**Decision**: JSON with `--path` export/import for maximum interoperability. We use Python's built-in `json` module with `indent=2` for readability. Export format includes a `"$schema"` field for IDE validation.

---

## 9. Release Plan

### 9.1 Milestones

| Milestone | Timeline | Deliverables |
|-----------|----------|--------------|
| **M0: Project scaffold** | Week 1 | Project structure, CLI skeleton, `mcp list` (list manually registered servers) |
| **M1: Core install** | Week 2-3 | `mcp install` (git/npm/pip), `mcp remove`, `mcp info`, config manager |
| **M2: Registry & search** | Week 4 | `mcp search` (MCP.so + Smithery), `mcp install` auto-resolve from registry |
| **M3: Tool introspection** | Week 5 | MCP client with `tools/list`, `tools/call`; `mcp list --tools` |
| **M4: Proxy server** | Week 6-7 | `mcp serve` with OpenAI-compatible API, streaming support |
| **M5: Web UI** | Week 8 | `mcp explore`, FastAPI+HTMX dashboard, interactive tool tester |
| **M6: Sandbox** | Week 9-10 | `mcp sandbox on/off`, Docker backend, resource limits |
| **M7: Config import/export** | Week 10 | `mcp config export/import`, Claude Desktop config generation |
| **M8: Polish & release** | Week 11-12 | Documentation, tests (unit + integration), CI/CD, PyPI release |

### 9.2 Package Distribution

- **Primary**: PyPI (`pip install mcp-pm`)
- **Secondary**: npm (`npm install -g mcp-pm`) — wraps the Python package via `node-bind`
- **Future**: Homebrew formula, Docker image

### 9.3 Post-v1 Roadmap

| Feature | Priority | Description |
|---------|----------|-------------|
| HTTP/SSE transport | P1 | Connect to remote MCP servers (not just local subprocesses) |
| Plugin system | P1 | Allow third-party extensions to mcp-pm itself |
| Registry publishing | P2 | `mcp publish` to submit servers to a community registry |
| Windows support | P2 | Test and fix on Windows (WSL2 first, then native) |
| Auto-update | P2 | Self-update mechanism (`mcp update --self`) |
| Telemetry (opt-in) | P3 | Anonymous usage stats to improve registry ranking |
| Visual Studio Code extension | P3 | GUI for managing MCP servers inside VS Code |

---

## 10. Glossary

| Term | Definition |
|------|------------|
| **MCP** | Model Context Protocol — an open protocol by Anthropic for tool/context exchange with AI models |
| **MCP Server** | A process that implements the MCP protocol and exposes tools/resources |
| **Stdio Transport** | MCP communication over stdin/stdout of a subprocess |
| **SSE Transport** | MCP communication over Server-Sent Events (HTTP) |
| **Tool** | A function exposed by an MCP server that an AI model can call |
| **Registry** | An index/directory of MCP servers |
| **Sandbox** | Security isolation layer (Docker, chroot, etc.) for running untrusted servers |
| **OpenAI-Compatible API** | REST API that mimics the OpenAI Chat Completions format, enabling drop-in use with any OpenAI SDK client |
| **HTMX** | A JavaScript library for building interactive web UIs via HTML attributes, without complex frontend frameworks |
