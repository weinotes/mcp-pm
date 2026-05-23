<p align="center">
  <img src="https://img.shields.io/badge/mcp--pm-v0.1.0-blue?style=flat-square" alt="版本" />
  <img src="https://img.shields.io/pypi/v/mcp-pm?style=flat-square" alt="pypi" />
  <img src="https://img.shields.io/pypi/dm/mcp-pm?style=flat-square" alt="下载量" />
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-green?style=flat-square" alt="python" />
  <img src="https://img.shields.io/github/license/weinotes/mcp-pm?style=flat-square" alt="许可证" />
  <img src="https://img.shields.io/badge/MCP-兼容-8A2BE2?style=flat-square" alt="mcp" />
  <img src="https://img.shields.io/badge/欢迎PR-brightgreen?style=flat-square" alt="prs" />
  <img src="https://img.shields.io/badge/12-个子命令-34d399?style=flat-square" alt="subcommands" />
  <img src="https://img.shields.io/badge/5-个注册中心-fbbf24?style=flat-square" alt="registries" />
</p>

<div align="center">

中文 | [English](README.md)

</div>

<h1 align="center">⛭ mcp-pm — MCP 服务器的 Homebrew</h1>

<p align="center">
  <em>Model Context Protocol 生态系统的 CLI 包管理器。一条命令即可安装、搜索、运行和管理 MCP 服务器。</em>
</p>

<p align="center">
  <a href="#-快速开始">快速开始</a> •
  <a href="#-功能特性">功能特性</a> •
  <a href="#-命令大全">命令大全</a> •
  <a href="#-系统架构">系统架构</a> •
  <a href="#-对比">对比</a> •
  <a href="#-注册中心">注册中心</a>
</p>

---

## ✨ 快速开始

```bash
# 安装
pip install mcp-pm

# 跨 5 个注册中心搜索 MCP 服务器
mcp search filesystem

# 安装一个服务器
mcp install mcp-server-filesystem

# 列出已安装的服务器
mcp list

# 启动 Web UI 控制面板
mcp explore

# 在隔离沙箱中运行服务器
mcp sandbox my-server --level docker

# 启动 OpenAI 兼容的 HTTP 代理
mcp serve
```

> **还没有安装任何服务器？** 运行 `mcp search database` 从社区注册中心发现服务器，或 `mcp explore` 通过 Web 界面浏览。

---

## 🚀 功能特性

| 特性 | 描述 |
|------|------|
| **🔍 多注册中心搜索** | 同时搜索 **5 个注册中心** — Smithery(5,000+)、npm、PyPI、内置精选列表 |
| **📦 一键安装** | `mcp install <server>` — 从 npm、pip、git 或 Docker 安装 |
| **🔒 沙箱隔离** | 在隔离环境中运行不可信服务器（子进程、Docker） |
| **🌐 Web 控制面板** | 漂亮的深色主题 HTMX 仪表盘，可视化管理 |
| **⚡ OpenAI 代理** | 将所有 MCP 工具暴露为 OpenAI 兼容 API |
| **🛡️ `mcp doctor`** | 诊断工具，检查整个 MCP 环境健康状态 |
| **🔧 12 个命令** | 完整的生命周期管理 — install、uninstall、update、list、search、info、explore、serve、sandbox、config、doctor、run |
| **🌍 多语言 UI** | Web UI 支持 English 和 中文，可扩展到任意语言 |
| **📝 YAML 配置** | 人类可读的配置文件 `~/.mcp-pm/config.yaml` |
| **🎨 精美终端** | 漂亮的表格、彩色输出和进度动画 |

---

## 🎮 命令大全

| 命令 | 描述 | 示例 |
|------|------|------|
| `mcp install` | 安装 MCP 服务器 | `mcp install mcp-server-filesystem` |
| `mcp uninstall` | 卸载已安装的服务器 | `mcp uninstall my-server` |
| `mcp update` | 更新所有已安装的服务器 | `mcp update` |
| `mcp list` | 列出已安装的服务器和工具 | `mcp list` |
| `mcp search` | 跨所有注册中心搜索 | `mcp search database` |
| `mcp info` | 查看服务器详情 | `mcp info github` |
| `mcp explore` | 启动 Web UI 控制面板 | `mcp explore` |
| `mcp serve` | 启动 HTTP 代理服务 | `mcp serve` |
| `mcp sandbox` | 在沙箱中运行服务器 | `mcp sandbox my-server --level docker` |
| `mcp config` | 管理配置 | `mcp config get servers` |
| `mcp doctor` | 诊断安装健康状态 | `mcp doctor` |
| `mcp run` | 直接运行 MCP 工具 | `mcp run my-server tool-name` |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      用户界面                                │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐  │
│  │  CLI     │  │ Web UI     │  │ VS Code  │  │ CI/CD    │  │
│  │ 终端     │  │ 控制面板   │  │ 扩展     │  │ Actions  │  │
│  └────┬─────┘  └─────┬──────┘  └────┬─────┘  └────┬─────┘  │
└───────┼──────────────┼──────────────┼──────────────┼────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                   CLI 核心 (click + rich)                     │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  12个子命令: install · uninstall · list · search       ││
│  │  info · explore · serve · sandbox · config · update    ││
│  │  doctor · run                                           ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ Installer│  │ Config   │  │ Sandbox  │  │ HTTP Proxy  │ │
│  │ (多源)   │  │ (YAML)   │  │ (Docker  │  │ (OpenAI     │ │
│  │          │  │          │  │  隔离)   │  │  兼容)      │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘ │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    注册中心集成                               │
│  ┌────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Smithery   │  │ npm      │  │ PyPI     │  │ 内置精选 │  │
│  │ 5,000+ 个  │  │ 注册中心  │  │ 注册中心  │  │ 27 个    │  │
│  └────────────┘  └──────────┘  └──────────┘  └──────────┘  │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      执行环境                                │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ 子进程       │  │ Docker       │  │ OpenAI API 代理   │  │
│  │ 直接启动     │  │ 沙箱         │  │ MCP → OpenAI     │  │
│  └──────────────┘  └──────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 注册中心

mcp-pm 同时从 **5 个注册中心** 聚合 MCP 服务器：

| 注册中心 | 状态 | 服务器数量 | 类型 |
|----------|:----:|:----------:|:----:|
| **内置精选** | ✅ 始终可用 | 27 个 | 离线 |
| **Smithery** ([smithery.ai](https://smithery.ai)) | ✅ 在线 | 5,000+ | API |
| **npm** ([npmjs.com](https://npmjs.com)) | ✅ 在线 | 所有 mcp-server 包 | API |
| **PyPI** ([pypi.org](https://pypi.org)) | ✅ 在线 | 所有 MCP Python 包 | API |
| MCP.so | ⚠️ 已下线 | — | 优雅降级 |
| GitHub Registry | ⚠️ 暂时不可用 | — | 优雅降级 |

所有注册中心**并行查询**，3 秒超时——你总能快速获得结果。

---

## 🔄 对比

| 特性 | **mcp-pm** | MCP.so | Smithery | GitHub Registry |
|------|:----------:|:------:|:--------:|:---------------:|
| CLI 优先 | ✅ | ❌ | ❌ | ❌ |
| 离线模式（内置索引） | ✅ | ❌ | ❌ | ❌ |
| 沙箱隔离 | ✅ | ❌ | ❌ | ❌ |
| 交互式 TUI | ✅ | ❌ | ❌ | ❌ |
| 多注册中心搜索 | ✅ | ❌ | ❌ | ❌ |
| Web UI 控制面板 | ✅ | ✅ | ✅ | ✅ |
| 自动生成配置 | ✅ | ❌ | ❌ | ❌ |
| 开源 + 可自托管 | ✅ | ❌ | ❌ | ✅ |
| OpenAI 兼容代理 | ✅ | ❌ | ❌ | ❌ |
| 12 个子命令 | ✅ | — | — | — |

---

## 🛠️ 开发

```bash
# 克隆并设置
git clone https://github.com/weinotes/mcp-pm.git
cd mcp-pm
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,web]"

# 运行测试
python -m pytest tests/ -v --tb=short

# 启动 Web UI
mcp explore

# 代码检查
ruff check .
ruff format --check .
```

---

## 🤝 参与贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。

- **报告 Bug**：[提交 Issue](https://github.com/weinotes/mcp-pm/issues/new?template=bug_report.md)
- **建议功能**：[发起讨论](https://github.com/weinotes/mcp-pm/issues/new?template=feature_request.md)
- **安全问题**：查看 [SECURITY.md](SECURITY.md)

---

## 📄 许可证

MIT License — Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>

---

<p align="center">
  <sub>❤️ 由 Davey Wong 制作</sub>
</p>
