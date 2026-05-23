<p align="center">
  <img src="https://img.shields.io/badge/mcp--pm-v0.1.0-blue?style=flat-square" alt="版本" />
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-green?style=flat-square" alt="python" />
  <img src="https://img.shields.io/github/license/daveywong/mcp-pm?style=flat-square" alt="许可证" />
  <img src="https://img.shields.io/badge/MCP-兼容-8A2BE2?style=flat-square" alt="mcp" />
  <img src="https://img.shields.io/badge/欢迎PR-brightgreen?style=flat-square" alt="prs" />
</p>

<div align="center">

中文 | [English](README.md)

</div>

<h1 align="center">mcp-pm — MCP 服务器的 Homebrew</h1>

<p align="center">
  <em>Model Context Protocol 生态系统的 CLI 包管理器。一条命令即可安装、搜索、运行和管理 MCP 服务器。</em>
</p>

---

## 为什么选择 mcp-pm？

MCP 生态系统发展迅速，但非常碎片化。服务器分散在 npm、PyPI、GitHub 仓库和各种 URL 上。缺乏一种标准化的方式来**发现、安装、配置和运行**它们。

**mcp-pm** 通过扮演中央包管理器的角色来解决这个问题——就像是 MCP 服务器的 Homebrew。

| 问题 | mcp-pm 解决方案 |
|---|---|
| 到哪里找 MCP 服务器？ | `mcp search` + `mcp explore`（集成注册中心） |
| 如何安装？ | `mcp install <server>` — 一条命令 |
| 如何配置？ | 自动生成配置文件 |
| 如何安全运行？ | `mcp sandbox <server>` — 隔离执行 |
| 如何在本地运行？ | `mcp serve <server>` — 启动进程 |

## 快速开始

```bash
# 安装
pip install mcp-pm

# 搜索 MCP 服务器
mcp search filesystem

# 安装服务器
mcp install mcp-server-filesystem

# 列出已安装的服务器
mcp list

# 在本地运行服务器
mcp serve mcp-server-filesystem

# 交互式浏览注册中心
mcp explore

# 查看配置
mcp config
```

## 功能列表

| 命令 | 描述 | 示例 |
|---|---|---|
| `mcp install` | 从注册中心安装 MCP 服务器 | `mcp install mcp-server-filesystem` |
| `mcp list` | 列出所有已安装的 MCP 服务器 | `mcp list` |
| `mcp search` | 搜索注册中心中的 MCP 服务器 | `mcp search database` |
| `mcp explore` | 交互式 TUI 浏览器 | `mcp explore` |
| `mcp serve` | 启动本地 MCP 服务器进程 | `mcp serve my-server` |
| `mcp config` | 查看或编辑 mcp-pm 配置 | `mcp config --edit` |
| `mcp sandbox` | 在隔离沙箱中运行服务器 | `mcp sandbox untrusted-server` |

## 架构

```
┌──────────────────────────────────────────────┐
│              用户 (CLI / 终端)                 │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│           mcp CLI (click + rich)               │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┐ │
│  │install│ list │search│explore│serve │config│ │
│  │ sandbox                                    │
│  └──────┴──────┴──────┴──────┴──────┴──────┘ │
└──────────────────┬───────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌───────────────┐    ┌────────────────┐
│ 包管理器核心   │    │ 注册中心 API   │
│               │    │ (FastAPI)      │
│ ┌───────────┐ │    │ ┌────────────┐ │
│ │ 配置(YAML)│ │    │ │ 解析器     │ │
│ │ 沙箱隔离   │ │    │ │ 元数据     │ │
│ └───────────┘ │    │ │ 搜索       │ │
│               │    │ └────────────┘ │
└───────────────┘    └────────────────┘
```

## 竞品对比

| 特性 | **mcp-pm** | MCP.so | Smithery | GitHub Registry |
|---|---|---|---|---|
| CLI 优先 | :white_check_mark: | :x: | :x: | :x: |
| 离线模式 | :white_check_mark: | :x: | :x: | :x: |
| 沙箱隔离 | :white_check_mark: | :x: | :x: | :x: |
| 交互式 TUI | :white_check_mark: | :x: | :x: | :x: |
| 自动配置生成 | :white_check_mark: | :x: | :x: | :x: |
| 开源 + 可自托管 | :white_check_mark: | :x: | :x: | :x: |
| 服务端注册中心 | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Web UI | :x: | :white_check_mark: | :white_check_mark: | :white_check_mark: |

## 贡献指南

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。

## 许可证

MIT 许可证 — 版权所有 (c) 2025-2026 Davey Wong &lt;wgwcko@gmail.com&gt;

---

<p align="center">
  <sub>❤️ 由 Davey Wong 制作</sub>
</p>
