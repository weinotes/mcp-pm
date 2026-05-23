# MCP-PM 公共 API 规范

> **项目**: mcp-pm (Model Context Protocol Package Manager)
> **定位**: "Homebrew for MCP Servers" — 统一的 MCP 服务器包管理器
> **作者**: Davey Wong \<wgwcko@gmail.com\>
> **技术栈**: Python 3.11+, Click, Rich, FastAPI+HTMX, httpx, Pydantic, asyncio

---

## 目录

1. [CLI 命令参考](#1-cli-命令参考)
2. [OpenAI 兼容 HTTP API](#2-openai-兼容-http-api)
3. [Web UI 路由](#3-web-ui-路由)
4. [配置文件格式](#4-配置文件格式)

---

## 1. CLI 命令参考

所有 CLI 命令通过 `mcp-pm` 入口点调用，底层使用 Click 框架 + Rich 终端输出。

### 1.1 全局选项

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--help` | flag | - | 显示帮助信息 |
| `--version` | flag | - | 显示版本号 |
| `--profile` | string | `default` | 指定配置 profile |
| `--verbose` | flag | `False` | 输出详细日志 |
| `--json` | flag | `False` | 以 JSON 格式输出 |

### 1.2 `mcp-pm install`

安装 MCP 服务器。支持从注册中心自动解析安装方式，也支持从 Git/npm/pip 直接安装。

```bash
mcp-pm install <server> [options]
```

**参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `server` | string | ✅ | 服务器名称或安装源 URL |

**选项**:

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--from`, `-f` | enum | `auto` | 安装源类型: `auto`, `git`, `npm`, `pip`, `docker` |
| `--version`, `-v` | string | `latest` | 指定安装版本 (semver) |
| `--sandbox` | flag | `False` | 启用沙箱隔离 |
| `--force` | flag | `False` | 强制安装（覆盖已有） |
| `--no-deps` | flag | `False` | 跳过依赖安装 |
| `--registry` | string | `auto` | 指定注册中心源 |

**示例**:

```bash
# 从注册中心自动安装
mcp-pm install @anthropic/calculator

# 从 Git 仓库安装
mcp-pm install git+https://github.com/org/mcp-server.git --version v1.2.0

# 从 npm 安装
mcp-pm install npm:@org/server-name

# 从 pip 安装
mcp-pm install pip:mcp-server-pkg --sandbox

# 强制安装指定版本
mcp-pm install @org/server --version 2.0.0 --force
```

### 1.3 `mcp-pm uninstall`

卸载已安装的 MCP 服务器。

```bash
mcp-pm uninstall <server> [options]
```

**参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `server` | string | ✅ | 服务器名称 |

**选项**:

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--purge` | flag | `False` | 同时删除缓存数据和日志 |
| `--yes`, `-y` | flag | `False` | 跳过确认提示 |

### 1.4 `mcp-pm list`

列出所有已安装的 MCP 服务器及其状态。

```bash
mcp-pm list [options]
```

**选项**:

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--tools` | flag | `False` | 同时列出每个服务器提供的所有工具 |
| `--json` | flag | `False` | JSON 格式输出 |
| `--status` | enum | `all` | 过滤状态: `all`, `active`, `disabled`, `error` |

**示例输出** (table):

```
┌──────────────────────┬──────────┬────────┬──────────┬──────────┐
│ Name                 │ Version  │ Status │ Transport│ Tools    │
├──────────────────────┼──────────┼────────┼──────────┼──────────┤
│ @anthropic/calculator│ 1.2.3    │ active │ stdio    │ 3        │
│ @org/server-name     │ 2.0.0    │ active │ stdio    │ 5        │
└──────────────────────┴──────────┴────────┴──────────┴──────────┘
```

### 1.5 `mcp-pm search`

从注册中心搜索 MCP 服务器包。

```bash
mcp-pm search <query> [options]
```

**参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `query` | string | ✅ | 搜索关键词，支持模糊匹配 |

**选项**:

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--limit`, `-l` | int | `20` | 最大返回数量 (1–100) |
| `--source`, `-s` | enum | `all` | 注册中心源: `all`, `mcp.so`, `smithery`, `github` |
| `--tag` | string | - | 按分类标签过滤 |

### 1.6 `mcp-pm info`

查看 MCP 服务器的详细信息。

```bash
mcp-pm info <server> [options]
```

**参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `server` | string | ✅ | 服务器名称 |

**选项**:

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--tools` | flag | `True` | 显示工具列表 |
| `--json` | flag | `False` | JSON 格式输出 |

### 1.7 `mcp-pm explore`

在浏览器中打开 Web Dashboard，可视化浏览和测试所有已安装工具。

```bash
mcp-pm explore [options]
```

**选项**:

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--port`, `-p` | int | `3000` | Web UI 监听端口 |
| `--host` | string | `127.0.0.1` | 绑定地址 |
| `--open` | flag | `True` | 自动在浏览器中打开 |
| `--no-open` | flag | `False` | 不自动打开浏览器 |

### 1.8 `mcp-pm serve`

启动 OpenAI 兼容的 HTTP 代理服务器，将所有已安装 MCP 工具暴露为标准 API。

```bash
mcp-pm serve [<host>:<port>] [options]
```

**位置参数**:

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `bind` | string | `127.0.0.1:8080` | 监听地址和端口 |

**选项**:

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--api-key`, `-k` | string | - | API 密钥认证 |
| `--stream` | flag | `True` | 启用 SSE 流式响应 |
| `--no-stream` | flag | `False` | 禁用流式响应 |
| `--reload` | flag | `False` | 开发模式热重载 |

### 1.9 `mcp-pm config`

配置管理：查看、设置、导出和导入配置。

```bash
mcp-pm config <subcommand> [options]
```

**子命令**:

#### `mcp-pm config show`

显示当前配置。

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--json` | flag | `False` | JSON 格式输出 |

#### `mcp-pm config set <key> <value>`

设置配置项。支持点号分隔的嵌套路径。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `key` | string | ✅ | 配置路径，如 `sandbox.docker.memory_limit` |
| `value` | string | ✅ | 配置值 |

#### `mcp-pm config export [--path <file>]`

导出配置为 JSON 文件。

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--path` | string | `stdout` | 导出文件路径 |

#### `mcp-pm config import <file>`

从 JSON 文件导入配置。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `file` | string | ✅ | 配置导入文件路径 |

#### `mcp-pm config set-env <server> <key>=<value>`

设置 MCP 服务器的环境变量（自动加密存储）。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `server` | string | ✅ | 服务器名称 |
| `key=value` | string | ✅ | 环境变量键值对 |

**示例**:

```bash
# 查看配置
mcp-pm config show

# 设置配置项
mcp-pm config set proxy.port 9090

# 导出配置
mcp-pm config export --path ./mcp-config-backup.json

# 导入配置
mcp-pm config import ./mcp-config-backup.json

# 设置服务器环境变量
mcp-pm config set-env @anthropic/calculator OPENAI_API_KEY=sk-xxx
```

### 1.10 `mcp-pm sandbox`

沙箱安全隔离管理。

```bash
mcp-pm sandbox <subcommand> [options]
```

**子命令**:

#### `mcp-pm sandbox on`

启用沙箱隔离。

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--engine` | enum | `docker` | 沙箱引擎: `venv`, `docker`, `subprocess` |
| `--all` | flag | `False` | 对所有已安装服务器启用 |

#### `mcp-pm sandbox off`

禁用沙箱隔离。

#### `mcp-pm sandbox status`

查看当前沙箱状态。

### 1.11 `mcp-pm doctor`

诊断系统环境与配置状态。

```bash
mcp-pm doctor [options]
```

**选项**:

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--fix` | flag | `False` | 自动修复可修复的问题 |

### 1.12 `mcp-pm run`

直接运行 MCP 服务器（stdio 模式），用于快速测试。

```bash
mcp-pm run <server> [options]
```

**参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `server` | string | ✅ | 服务器名称 |

**选项**:

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--tool` | string | - | 指定要调用的工具名称 |
| `--args` | JSON string | - | 工具参数 JSON |

### 1.13 `mcp-pm update`

更新已安装的 MCP 服务器。

```bash
mcp-pm update [server] [options]
```

**参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `server` | string | - | 服务器名称（为空则更新所有） |

**选项**:

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--dry-run` | flag | `False` | 预览更新，不实际执行 |

---

## 2. OpenAI 兼容 HTTP API

代理服务器 (`mcp-pm serve`) 提供 OpenAI API 兼容的 HTTP 端点。所有已安装 MCP 服务器的工具通过单一端点暴露。

### 2.1 基础配置

| 项目 | 值 |
|------|-----|
| **Base URL** | `http://127.0.0.1:8080` (默认) |
| **认证** | `Authorization: Bearer <api_key>` (可选) |
| **响应格式** | JSON / SSE (streaming) |

### 2.2 `POST /v1/chat/completions`

将 OpenAI 格式的聊天补全请求中的工具调用路由到对应的 MCP 服务器。

#### 请求

```json
{
  "model": "any",
  "messages": [
    {
      "role": "user",
      "content": "What's the weather in Tokyo?"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "weather__get_forecast",
        "description": "Get weather forecast for a city",
        "parameters": {
          "type": "object",
          "properties": {
            "city": {
              "type": "string",
              "description": "City name"
            }
          },
          "required": ["city"]
        }
      }
    }
  ],
  "stream": false
}
```

#### 请求字段

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `model` | string | ✅ | 模型标识符（当前忽略，保留兼容性） |
| `messages` | array | ✅ | 对话消息数组 |
| `tools` | array | ❌ | 工具定义数组（OpenAI tool_calls 格式） |
| `stream` | bool | ❌ | 是否使用 SSE 流式响应 (默认 `false`) |
| `temperature` | float | ❌ | 采样温度 (未使用，保留兼容性) |
| `max_tokens` | int | ❌ | 最大 token 数 (未使用，保留兼容性) |

#### 响应（非流式）

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1716547200,
  "model": "mcp-pm",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_xxx",
            "type": "function",
            "function": {
              "name": "weather__get_forecast",
              "arguments": "{\"city\":\"Tokyo\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | string | 唯一请求 ID |
| `object` | string | 固定值 `chat.completion` |
| `created` | int | Unix 时间戳 |
| `choices[].message.role` | string | 固定值 `assistant` |
| `choices[].message.content` | string\|null | 文本回复（工具调用时为 null） |
| `choices[].message.tool_calls[].id` | string | 工具调用 ID |
| `choices[].message.tool_calls[].type` | string | 固定值 `function` |
| `choices[].message.tool_calls[].function.name` | string | 工具完整名称 (`<server>__<tool>`) |
| `choices[].message.tool_calls[].function.arguments` | string | JSON 序列化的参数对象 |
| `choices[].finish_reason` | string | `stop`, `tool_calls`, `length` 或 `error` |
| `usage` | object | Token 用量统计 |

#### 流式响应 (SSE)

当 `stream: true` 时，返回 Server-Sent Events 流：

```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_xxx","type":"function","function":{"name":"weather__get_forecast","arguments":"{\"city\":"}}]},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\"Tokyo\"}"}}]},"finish_reason":null}]}

data: [DONE]
```

#### 错误响应

```json
{
  "error": {
    "message": "Tool 'weather__get_forecast' not found in any installed MCP server",
    "type": "invalid_request_error",
    "code": "tool_not_found"
  }
}
```

**错误码**:

| HTTP 状态码 | error.code | 描述 |
|-------------|------------|------|
| 400 | `invalid_request_error` | 请求格式错误或缺少必填字段 |
| 401 | `authentication_error` | API Key 无效或缺失 |
| 404 | `tool_not_found` | 指定的工具不存在 |
| 500 | `internal_error` | MCP 服务器内部错误 |
| 503 | `server_unavailable` | MCP 服务器进程不可用 |

### 2.3 工具命名约定

为避免跨服务器的工具名称冲突，代理使用双下划线分隔符：

```
<server_name>__<tool_name>
```

**示例**:

| 注册的工具 | 完整名称 |
|------------|----------|
| `calculator` (来自 `@anthropic/calculator`) | `@anthropic/calculator__calculator` |
| `get_forecast` (来自 `weather-server`) | `weather-server__get_forecast` |
| `search` (来自 `web-search`) | `web-search__search` |

### 2.4 `POST /v1/tools/list`

列出所有已安装 MCP 服务器暴露的工具。

#### 响应

```json
{
  "tools": [
    {
      "name": "weather-server__get_forecast",
      "description": "Get weather forecast for a city",
      "input_schema": {
        "type": "object",
        "properties": {
          "city": {
            "type": "string",
            "description": "City name"
          }
        },
        "required": ["city"]
      },
      "server": "weather-server"
    }
  ]
}
```

### 2.5 `POST /v1/tools/call`

直接调用指定工具（绕过 chat completions 层）。

#### 请求

```json
{
  "name": "weather-server__get_forecast",
  "arguments": {
    "city": "Tokyo"
  }
}
```

#### 响应

```json
{
  "content": [
    {
      "type": "text",
      "text": "The weather in Tokyo is 22°C and sunny."
    }
  ],
  "is_error": false
}
```

### 2.6 `GET /v1/models`

列出所有可用模型（映射到已安装的 MCP 服务器）。

```json
{
  "object": "list",
  "data": [
    {
      "id": "@anthropic/calculator",
      "object": "model",
      "created": 1716547200,
      "owned_by": "mcp-pm"
    },
    {
      "id": "weather-server",
      "object": "model",
      "created": 1716547200,
      "owned_by": "mcp-pm"
    }
  ]
}
```

---

## 3. Web UI 路由

Web Dashboard (`mcp-pm explore`) 基于 FastAPI + HTMX + Jinja2 构建。

### 3.1 页面路由

| 方法 | 路由 | 描述 | 模板 |
|------|------|------|------|
| `GET` | `/` | Dashboard 首页 — 服务器概览、状态、工具统计 | `index.html` |
| `GET` | `/tools/{name}` | 工具详情页 — 查看工具的 JSON Schema 并在线调用 | `tool_detail.html` |
| `GET` | `/config` | 配置编辑器 — 查看和修改 mcp-pm 配置 | `config.html` |
| `GET` | `/logs` | 日志查看器 — 实时显示 MCP 服务器日志 | `logs.html` |
| `GET` | `/servers` | 服务器列表 — 管理安装/卸载/更新 | `servers.html` |
| `GET` | `/servers/{name}` | 服务器详情 — 版本、环境变量、工具列表 | `server_detail.html` |
| `GET` | `/install` | 安装向导 — 搜索并安装新服务器 | `install.html` |

### 3.2 API 路由 (Web UI 内部使用)

| 方法 | 路由 | 描述 |
|------|------|------|
| `GET` | `/api/servers` | 获取所有服务器状态 |
| `GET` | `/api/servers/{name}` | 获取单个服务器信息 |
| `POST` | `/api/servers/{name}/start` | 启动服务器 |
| `POST` | `/api/servers/{name}/stop` | 停止服务器 |
| `POST` | `/api/servers/{name}/restart` | 重启服务器 |
| `DELETE` | `/api/servers/{name}` | 卸载服务器 |
| `GET` | `/api/tools/{name}` | 获取工具详情 |
| `POST` | `/api/tools/{name}/call` | 调用工具（测试沙箱） |
| `GET` | `/api/logs` | 获取日志（SSE 实时推送） |
| `GET` | `/api/logs/{server}` | 获取指定服务器日志 |
| `GET` | `/api/config` | 获取当前配置 |
| `PUT` | `/api/config` | 更新配置 |
| `POST` | `/api/install` | 触发安装请求 |
| `GET` | `/api/search?q={query}` | 搜索注册中心 |

### 3.3 SSE 端点

| 方法 | 路由 | 描述 |
|------|------|------|
| `GET` | `/api/events` | 全局事件流（服务器状态变更、安装进度） |
| `GET` | `/api/logs/stream` | 实时日志流 |

---

## 4. 配置文件格式

主配置文件位于 `~/.config/mcp-pm/config.yaml`，使用 YAML 格式。

### 4.1 YAML Schema 定义

```yaml
# ~/.config/mcp-pm/config.yaml
# mcp-pm 主配置文件

# --- 版本标识 ---
version: 1                        # 配置格式版本

# --- 注册中心配置 ---
registry:
  url: "https://registry.mcp-pm.dev"   # 注册中心 API 地址
  api_key: null                         # API 密钥（可选）
  sources:                              # 注册中心源配置
    mcp_so:
      enabled: true
    smithery:
      enabled: true
    github:
      enabled: false

# --- Profile 配置 ---
profiles:
  default:                              # 默认 profile
    servers:                            # 已安装的 MCP 服务器列表
      - name: "@anthropic/calculator"
        version: "1.2.3"
        transport: stdio                # 传输协议: stdio | http
        sandbox: null                   # 沙箱类型: null | venv | docker
        enabled: true                   # 启用状态
        env:                            # 环境变量（敏感值存储在 secrets/ 目录）
          OPENAI_API_KEY: "sk-xxx"

      - name: "weather-server"
        version: "2.0.0"
        transport: stdio
        sandbox: docker
        enabled: true
        env: {}

    hooks:                              # 安装/卸载钩子
      pre_install: []
      post_install: []
      pre_uninstall: []
      post_uninstall: []

# --- 工作区配置 ---
workspaces:
  current: default                      # 当前活动 profile

# --- 代理服务器配置 ---
proxy:
  host: "127.0.0.1"                    # 绑定地址
  port: 8080                            # 监听端口
  api_key: null                         # API 密钥（空则不启用认证）
  stream: true                          # 默认启用流式响应

# --- Web UI 配置 ---
web:
  host: "127.0.0.1"                    # 绑定地址
  port: 3000                            # 监听端口
  open_browser: true                    # 启动时自动打开浏览器

# --- 沙箱配置 ---
sandbox:
  default_engine: "subprocess"          # 默认隔离策略: subprocess | venv | docker
  docker:
    default_image: "python:3.11-slim"   # Docker 基础镜像
    memory_limit: "512m"                # 内存限制
    cpu_limit: 0.5                      # CPU 核心限制
    network_access: []                  # 允许访问的网络地址白名单
  subprocess:
    env_clean: true                     # 清理继承的环境变量
    timeout: 30                         # 子进程启动超时（秒）

# --- 日志配置 ---
logging:
  level: "INFO"                         # 日志级别: DEBUG | INFO | WARNING | ERROR | CRITICAL
  file: "~/.local/share/mcp-pm/logs/mcp-pm.log"
  audit: "~/.local/share/mcp-pm/logs/audit.log"
  max_size: 10485760                    # 单文件最大字节 (10MB)
  backup_count: 5                       # 保留的日志文件数
```

### 4.2 数据结构定义 (Python/Pydantic)

```python
from typing import Literal
from pydantic import BaseModel, Field

class RegistrySourceConfig(BaseModel):
    enabled: bool = True

class RegistryConfig(BaseModel):
    url: str = "https://registry.mcp-pm.dev"
    api_key: str | None = None
    sources: dict[str, RegistrySourceConfig] = {
        "mcp_so": RegistrySourceConfig(),
        "smithery": RegistrySourceConfig(),
        "github": RegistrySourceConfig(enabled=False),
    }

class ServerEntry(BaseModel):
    name: str
    version: str
    transport: Literal["stdio", "http"] = "stdio"
    sandbox: Literal["venv", "docker", "subprocess", None] = None
    enabled: bool = True
    env: dict[str, str] = Field(default_factory=dict)

class ProfileConfig(BaseModel):
    servers: list[ServerEntry] = Field(default_factory=list)
    hooks: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "pre_install": [],
            "post_install": [],
            "pre_uninstall": [],
            "post_uninstall": [],
        }
    )

class ProxyConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    api_key: str | None = None
    stream: bool = True

class WebConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3000
    open_browser: bool = True

class SandboxDockerConfig(BaseModel):
    default_image: str = "python:3.11-slim"
    memory_limit: str = "512m"
    cpu_limit: float = 0.5
    network_access: list[str] = Field(default_factory=list)

class SandboxSubprocessConfig(BaseModel):
    env_clean: bool = True
    timeout: int = 30

class SandboxConfig(BaseModel):
    default_engine: Literal["subprocess", "venv", "docker"] = "subprocess"
    docker: SandboxDockerConfig = Field(default_factory=SandboxDockerConfig)
    subprocess: SandboxSubprocessConfig = Field(default_factory=SandboxSubprocessConfig)

class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "~/.local/share/mcp-pm/logs/mcp-pm.log"
    audit: str = "~/.local/share/mcp-pm/logs/audit.log"
    max_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

class McpConfig(BaseModel):
    version: int = 1
    registry: RegistryConfig = Field(default_factory=RegistryConfig)
    profiles: dict[str, ProfileConfig] = {
        "default": ProfileConfig()
    }
    workspaces: dict[str, str] = {"current": "default"}
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
```

### 4.3 服务器 Manifest 格式

每个安装的 MCP 服务器在 `~/.mcp/servers/<name>/manifest.json` 中保存其运行时信息：

```json
{
  "name": "@anthropic/calculator",
  "version": "1.2.3",
  "source": {
    "type": "npm",
    "url": "npm:@anthropic/calculator",
    "ref": "1.2.3"
  },
  "runtime": {
    "command": "node",
    "args": ["path/to/server/build/index.js"],
    "env": {}
  },
  "tools": [
    {
      "name": "calculate",
      "description": "Perform a calculation",
      "input_schema": {
        "type": "object",
        "properties": {
          "expression": {
            "type": "string",
            "description": "Math expression to evaluate"
          }
        },
        "required": ["expression"]
      }
    }
  ],
  "sandbox": {
    "enabled": false,
    "engine": null
  },
  "installed_at": "2026-05-24T00:35:00Z",
  "updated_at": "2026-05-24T00:35:00Z",
  "status": "active"
}
```

### 4.4 密钥存储

敏感信息（API Key、Token）存储在 `~/.mcp/secrets/` 目录，文件权限为 `600`：

```
~/.mcp/secrets/
├── @anthropic/calculator.json        # 每个服务器的加密环境变量
└── proxy-api-key.enc                 # 代理服务器 API 密钥（加密存储）
```
