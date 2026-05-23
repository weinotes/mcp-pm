# MCP-PM 系统架构文档

> **项目定位**: "Homebrew for MCP Servers" — 统一的 MCP 服务器包管理器
>
> **技术栈**: Python 3.11+ · Click (CLI) · Rich (终端输出) · FastAPI+HTMX (Web UI)
> httpx (HTTP客户端) · Pydantic (数据模型) · asyncio (异步运行时)
>
> **作者**: Davey Wong <wgwcko@gmail.com> · **协议**: MIT

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    用户交互层                            │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │  CLI (Click+Rich) │  │  Web Dashboard (FastAPI+HTMX)│  │
│  │  src/mcp_pm/cli.py│  │  src/mcp_pm/webui/          │  │
│  └────────┬─────────┘  └────────┬─────────────────────┘  │
└───────────┼─────────────────────┼─────────────────────────┘
            │                     │
            ▼                     ▼
┌─────────────────────────────────────────────────────────┐
│                    业务逻辑层                            │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐ │
│  │ Registry │ │ Installer│ │Client  │ │ Sandbox      │ │
│  │ 客户端   │ │ 安装/卸载 │ │MCP运行 │ │ 安全隔离     │ │
│  │ registry │ │ installer│ │ client │ │ sandbox      │ │
│  │  .py     │ │  .py     │ │ .py    │ │  .py         │ │
│  └────┬─────┘ └────┬─────┘ └───┬────┘ └──────┬───────┘ │
│       │            │           │              │         │
│       └────────────┼───────────┼──────────────┘         │
│                    ▼           ▼                        │
│            ┌────────────┐ ┌────────┐                    │
│            │  Config    │ │ Server │                    │
│            │  配置管理   │ │ HTTP代理│                   │
│            │ config.py  │ │server.py│                   │
│            └────────────┘ └────────┘                    │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    外部基础设施                          │
│  ┌──────────────┐  ┌──────────────────┐                 │
│  │ MCP Registry │  │ MCP Server 进程   │                 │
│  │ (远端注册中心)│  │ (stdio/HTTP)     │                 │
│  └──────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

### 模块依赖关系

```
mcp-pm
 ├── cli.py              ← 入口点，依赖所有模块
 │    ├── registry.py    ← 查询/发布服务器
 │    ├── installer.py   ← 安装/卸载/更新
 │    ├── client.py      ← 运行时交互
 │    ├── server.py      ← 代理服务
 │    ├── config.py      ← 配置读写
 │    ├── webui/         ← Web 界面
 │    └── sandbox.py     ← 安全隔离
 ├── config.py           ← 被所有模块依赖
 ├── installer.py        ← 依赖 registry, config, sandbox
 ├── client.py           ← 依赖 config
 ├── server.py           ← 依赖 client, config
 ├── webui/              ← 依赖 installer, registry, client, config
 └── sandbox.py          ← 独立
```

---

## 2. 核心数据流

### 2.1 安装流程

```
用户: mcp-pm install <server-name>
       │
       ▼
  cli.py (Click 解析参数)
       │
       ▼
  registry.py ──HTTP──► MCP Registry API
       │                    │
       │              ◄── 返回包元数据
       │                   (name, version, download_url, dependencies)
       ▼
  installer.py
       │
       ├── 1. 创建虚拟环境 / 容器 (sandbox.py)
       ├── 2. 下载并安装包
       ├── 3. 写入 config.py 配置
       └── 4. 验证安装 (client.py 测试连接)
       │
       ▼
  Rich 输出安装结果
```

### 2.2 运行时交互

```
用户: mcp-pm run <server-name>
       │
       ▼
  cli.py → client.py
       │
       ├── stdio 模式: spawn 子进程 → stdin/stdout MCP 协议
       └── HTTP 模式: 启动 server.py → OpenAI 兼容 API
              │
              ▼
          AI 应用 (cursor, claude, etc.)
```

---

## 3. 各组件详细说明

### 3.1 `src/mcp_pm/cli.py` — CLI 入口

**职责**:
- Click 命令定义，作为整个项目的 CLI facade
- 提供 `install`, `uninstall`, `list`, `search`, `info`, `run`, `server`, `config`, `doctor` 等子命令
- 参数解析与验证
- Rich 控制台输出格式化
- 错误处理与帮助信息

**关键命令**:

| 命令 | 功能 | 对应后端模块 |
|------|------|-------------|
| `install` | 安装 MCP 服务器 | installer.py |
| `uninstall` | 卸载 MCP 服务器 | installer.py |
| `list` | 列出已安装服务器 | config.py |
| `search` | 搜索注册中心 | registry.py |
| `info` | 查看服务器详情 | registry.py |
| `run` | 直接运行服务器 | client.py |
| `server` | 启动 HTTP 代理 | server.py |
| `config` | 管理配置 | config.py |
| `doctor` | 诊断系统状态 | 多模块 |

### 3.2 `src/mcp_pm/registry.py` — 注册中心客户端

**职责**:
- 与远端 MCP Registry API 通信
- 搜索和发现 MCP 服务器包
- 获取包元数据（版本、依赖、下载地址）
- 发布新包到注册中心（可选）

**核心接口**:

```python
class RegistryClient:
    async def search(self, query: str) -> list[PackageInfo]
    async def get_package(self, name: str) -> PackageInfo
    async def list_packages(self, page: int) -> PaginatedResult
    async def publish(self, package: PackageManifest) -> bool
```

**数据流**: `cli.py` → `registry.py` → HTTP (httpx) → Registry API

### 3.3 `src/mcp_pm/installer.py` — 安装/卸载逻辑

**职责**:
- 执行 MCP 服务器的安装、卸载、升级
- 创建隔离环境（sandbox）
- 管理版本和依赖
- 后安装验证

**安装流程**:

```
1. 解析包元数据 (registry)
2. 检查依赖冲突 (config)
3. 创建沙箱环境 (sandbox)
4. pip install / 二进制下载
5. 注册到本地配置 (config)
6. 运行 smoke test (client)
```

**关键方法**:

```python
class Installer:
    async def install(self, name: str, version: str | None) -> InstallResult
    async def uninstall(self, name: str) -> bool
    async def update(self, name: str) -> InstallResult
    async def list_installed(self) -> list[InstalledPackage]
```

### 3.4 `src/mcp_pm/client.py` — MCP 客户端运行时

**职责**:
- 管理 MCP 服务器进程生命周期
- 支持 stdio 和 HTTP 两种传输协议
- 实现 MCP 协议的消息封装与解析
- 提供 `list_tools`, `call_tool`, `list_resources`, `read_resource` 等核心操作

**架构设计**:

```
MCPClient
  ├── StdioTransport    # 子进程 stdin/stdout
  │     └── JSON-RPC over stdio
  └── HTTPTransport     # HTTP 长连接
        └── JSON-RPC over HTTP SSE
```

**关键接口**:

```python
class MCPClient:
    async def connect(self, transport: TransportConfig)
    async def list_tools(self) -> list[Tool]
    async def call_tool(self, name: str, args: dict) -> ToolResult
    async def list_resources(self) -> list[Resource]
    async def read_resource(self, uri: str) -> ResourceContent
    async def close(self)
```

### 3.5 `src/mcp_pm/config.py` — 配置管理

**职责**:
- 管理本地配置文件的读写
- 维护已安装 MCP 服务器清单
- 支持多 profile / 工作区
- 配置验证与迁移

**配置存储格式** (YAML/JSON):

```yaml
# ~/.config/mcp-pm/config.yaml
registry:
  url: https://registry.mcp-pm.dev
  api_key: "..."

profiles:
  default:
    servers:
      - name: "@org/server-name"
        version: "1.2.3"
        transport: stdio
        sandbox: venv
        env:
          OPENAI_API_KEY: "..."

workspaces:
  current: default
```

**核心模型**:

```python
@dataclass
class McpConfig:
    registry: RegistryConfig
    profiles: dict[str, ProfileConfig]
    workspaces: WorkspaceConfig

@dataclass
class ServerEntry:
    name: str
    version: str
    transport: Literal["stdio", "http"]
    sandbox: str | None
    env: dict[str, str]
```

### 3.6 `src/mcp_pm/server.py` — HTTP 代理服务器

**职责**:
- 启动一个 HTTP 服务器，暴露 OpenAI-compatible API
- 将 OpenAI API 调用转换为 MCP 协议调用
- 支持多个 MCP 服务器的路由和负载分发
- 提供 SSE (Server-Sent Events) 流式响应

**API 兼容**:

| OpenAI Endpoint | 映射到 MCP 操作 |
|----------------|----------------|
| `POST /v1/chat/completions` | 调用 tools + 组合响应 |
| `POST /v1/tools/list` | `list_tools()` |
| `POST /v1/tools/call` | `call_tool()` |
| `GET /v1/models` | `list_tools()` 聚合 |

**实现**:

```python
# FastAPI 应用
app = FastAPI()

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    # 1. 解析 messages, tools
    # 2. 构建 MCP 调用链
    # 3. 流式 SSE 返回
    ...

@app.post("/v1/tools/call")
async def tool_call(request: ToolCallRequest):
    # 路由到对应 MCP server
    async with MCPClient(config) as client:
        return await client.call_tool(request.name, request.args)
```

### 3.7 `src/mcp_pm/webui/` — Web Dashboard

**职责**:
- 提供美观的 Web 管理界面
- 安装、卸载、管理 MCP 服务器
- 实时查看服务器状态和日志
- 配置管理界面

**技术实现**:
- FastAPI 提供后端 API
- HTMX + Jinja2 模板渲染前端
- 异步 SSE 推送状态更新
- 静态资源（CSS/JS）内嵌

**目录结构**:

```
webui/
  ├── __init__.py       # FastAPI router
  ├── templates/        # Jinja2 模板
  │   ├── index.html
  │   ├── install.html
  │   └── server_detail.html
  └── static/           # CSS, JS, 图标
      ├── app.css
      └── app.js
```

### 3.8 `src/mcp_pm/sandbox.py` — 沙箱安全隔离

**职责**:
- 为每个 MCP 服务器创建隔离的运行环境
- 支持多种隔离策略
- 限制资源使用（CPU, 内存, 网络）
- 提供清理机制

**隔离策略**:

| 策略 | 实现 | 安全级别 | 适用场景 |
|------|------|---------|---------|
| `venv` | Python venv | 低 | 官方/可信包 |
| `docker` | Docker 容器 | 高 | 第三方/社区包 |
| `subprocess` | 子进程 + seccomp | 中 | 本地开发 |

**关键方法**:

```python
class Sandbox:
    async def create(self, server_name: str, strategy: str) -> SandboxEnv
    async def execute(self, env: SandboxEnv, command: list[str]) -> ExecutionResult
    async def destroy(self, env: SandboxEnv)
    def get_path(self, env: SandboxEnv) -> str
```

---

## 4. 核心数据结构

### 4.1 包信息 (PackageInfo)

```python
@dataclass
class PackageInfo:
    name: str                    # 完整包名 (e.g. "@anthropic/calculator")
    version: str                  # semver 版本号
    description: str              # 简短描述
    author: str                   # 作者/组织
    license: str                  # 开源协议
    homepage: str | None          # 项目主页 URL
    repository: str | None        # 源码仓库 URL
    download_url: str             # 下载地址
    checksum: str                 # 完整性校验 (SHA256)
    dependencies: list[str]       # 依赖列表
    tags: list[str]               # 分类标签
    tools: list[ToolManifest]     # 暴露的工具声明
    resources: list[ResourceManifest]  # 暴露的资源声明
    transport: list[str]          # 支持的传输协议
```

### 4.2 工具声明 (ToolManifest)

```python
@dataclass
class ToolManifest:
    name: str                     # 工具名称
    description: str              # 工具描述
    input_schema: dict            # JSON Schema 输入格式
    output_schema: dict | None    # JSON Schema 输出格式
```

### 4.3 工具调用结果 (ToolResult)

```python
@dataclass
class ToolResult:
    content: list[ContentBlock]   # 结果内容
    is_error: bool = False        # 是否错误

@dataclass
class ContentBlock:
    type: Literal["text", "image", "resource", "embedding"]
    text: str | None
    data: str | None              # base64 编码数据
    mime_type: str | None
```

### 4.4 安装记录 (InstalledPackage)

```python
@dataclass
class InstalledPackage:
    name: str
    version: str
    path: str                     # 安装路径
    transport: str                # 传输协议类型
    sandbox_type: str             # 沙箱类型
    status: Literal["active", "disabled", "error"]
    installed_at: datetime
    updated_at: datetime
```

---

## 5. 错误处理策略

### 分层错误处理

```
CLI Layer (cli.py)
   └── 格式化用户友好的错误消息 (Rich)
        │
业务逻辑层 (installer, registry, client)
   └── 自定义异常层次
        │
基础设施层 (httpx, subprocess, disk)
   └── 捕获底层异常并包装
```

### 异常层次

```python
class McpPmError(Exception):          # 基类
    pass

class RegistryError(McpPmError):       # 注册中心错误
    """网络错误、认证失败、包不存在"""
    pass

class InstallError(McpPmError):        # 安装错误
    """依赖冲突、磁盘不足、版本不兼容"""
    pass

class ClientError(McpPmError):         # 运行时错误
    """连接失败、协议错误、超时"""
    pass

class ConfigError(McpPmError):         # 配置错误
    """配置格式错误、值验证失败"""
    pass

class SandboxError(McpPmError):        # 沙箱错误
    """隔离环境创建失败、资源耗尽"""
    pass
```

### 重试策略
- 网络操作: 指数退避重试 (3次, base=1s, max=10s)
- 安装操作: 失败后清理临时文件
- 运行时错误: 自动重启最多 3 次

---

## 6. 日志规范

### 日志级别

| 级别 | 用途 |
|------|------|
| DEBUG | 调试信息、API 请求/响应详情 |
| INFO | 常规操作: 安装、卸载、运行 |
| WARNING | 非致命问题: 版本过旧、配置弃用 |
| ERROR | 操作失败: 安装失败、连接断开 |
| CRITICAL | 系统级故障: 配置损坏、磁盘满 |

### 日志格式

```
[2024-01-01 12:00:00] [mcp-pm] [INFO] [installer] 安装包 @org/server-name@1.2.3
```

### 日志配置位置
- 控制台输出: stderr (开发模式)
- 文件日志: `~/.local/share/mcp-pm/logs/mcp-pm.log`
- 审计日志: `~/.local/share/mcp-pm/logs/audit.log` (安装/卸载操作)

---

## 7. 性能考量

### 异步设计
- 所有 I/O 操作基于 `asyncio`
- CLI 使用 `asyncio.run()` 驱动事件循环
- HTTP 客户端使用 `httpx.AsyncClient`
- Web UI 使用 FastAPI 原生 async handler

### 缓存策略
- 注册中心搜索结果缓存 5 分钟
- 包元数据缓存 1 小时
- 配置热加载，避免频繁磁盘读写

### 资源管理
- 沙箱按需创建，空闲 30 分钟后自动销毁
- HTTP 代理支持连接池复用
- 流式响应避免大内存占用

---

## 附录

### A. 模块文件清单

```
src/mcp_pm/
  ├── __init__.py          # 版本信息
  ├── __main__.py          # python -m 入口
  ├── cli.py               # Click CLI
  ├── registry.py          # 注册中心客户端
  ├── installer.py         # 安装器
  ├── client.py            # MCP 客户端
  ├── config.py            # 配置管理
  ├── server.py            # HTTP 代理
  ├── sandbox.py           # 沙箱隔离
  └── webui/
       ├── __init__.py
       ├── templates/
       └── static/
```

### B. 配置路径

| 用途 | 路径 |
|------|------|
| 用户配置 | `~/.config/mcp-pm/config.yaml` |
| 安装目录 | `~/.local/share/mcp-pm/servers/` |
| 缓存目录 | `~/.cache/mcp-pm/` |
| 日志目录 | `~/.local/share/mcp-pm/logs/` |
| 沙箱目录 | `~/.local/share/mcp-pm/sandboxes/` |
