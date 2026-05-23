<p align="center">
  <img src="https://img.shields.io/badge/mcp--pm-v0.1.0-blue?style=flat-square" alt="version" />
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-green?style=flat-square" alt="python" />
  <img src="https://img.shields.io/github/license/weinotes/mcp-pm?style=flat-square" alt="license" />
  <img src="https://img.shields.io/badge/MCP-Compatible-8A2BE2?style=flat-square" alt="mcp" />
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square" alt="prs" />
</p>

<div align="center">

[简体中文](README.zh-CN.md) | English

</div>

<h1 align="center">mcp-pm — Homebrew for MCP Servers</h1>

<p align="center">
  <em>A CLI package manager for the Model Context Protocol ecosystem. Install, search, serve, and manage MCP servers with a single command.</em>
</p>

---

## Why mcp-pm?

The MCP ecosystem is growing fast, but it's fragmented. Servers live across npm, PyPI, GitHub repos, and random URLs. There's no standardized way to **discover, install, configure, and run** them.

**mcp-pm** solves this by acting as a central package manager — think Homebrew, but for MCP servers.

| Problem | mcp-pm Solution |
|---|---|
| Where to find MCP servers? | `mcp search` + `mcp explore` (integrated registry) |
| How to install? | `mcp install <server>` — one command |
| How to configure? | Auto-generates config files |
| How to run safely? | `mcp sandbox <server>` — isolated execution |
| How to run locally? | `mcp serve <server>` — starts the process |

## Quick Start

```bash
# Install
pip install mcp-pm

# Search for MCP servers
mcp search filesystem

# Install a server
mcp install mcp-server-filesystem

# List installed servers
mcp list

# Serve a server locally
mcp serve mcp-server-filesystem

# Explore the registry interactively
mcp explore

# View configuration
mcp config
```

## Features

| Command | Description | Example |
|---|---|---|
| `mcp install` | Install an MCP server from the registry | `mcp install mcp-server-filesystem` |
| `mcp list` | List all installed MCP servers | `mcp list` |
| `mcp search` | Search the registry for MCP servers | `mcp search database` |
| `mcp explore` | Interactive TUI browser for discovery | `mcp explore` |
| `mcp serve` | Start a local MCP server process | `mcp serve my-server` |
| `mcp config` | View or edit mcp-pm configuration | `mcp config --edit` |
| `mcp sandbox` | Run a server in an isolated sandbox | `mcp sandbox untrusted-server` |

## Architecture

```
┌──────────────────────────────────────────────┐
│              User (CLI / Terminal)             │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│              mcp CLI (click + rich)           │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┐ │
│  │install│ list │search│explore│serve │config│ │
│  │ sandbox                                    │
│  └──────┴──────┴──────┴──────┴──────┴──────┘ │
└──────────────────┬───────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌───────────────┐    ┌────────────────┐
│ Package       │    │ Registry API   │
│ Manager Core  │    │ (FastAPI)      │
│ ┌───────────┐ │    │ ┌────────────┐ │
│ │ Config    │ │    │ │ Resolver   │ │
│ │ (YAML)    │ │    │ │ Metadata   │ │
│ │ Sandbox   │ │    │ │ Search     │ │
│ │ Isolation │ │    │ └────────────┘ │
│ └───────────┘ │    └────────────────┘
└───────────────┘
```

## Comparison

| Feature | **mcp-pm** | MCP.so | Smithery | GitHub Registry |
|---|---|---|---|---|
| CLI-first | :white_check_mark: | :x: | :x: | :x: |
| Offline mode | :white_check_mark: | :x: | :x: | :x: |
| Sandbox isolation | :white_check_mark: | :x: | :x: | :x: |
| Interactive TUI | :white_check_mark: | :x: | :x: | :x: |
| Auto-config generation | :white_check_mark: | :x: | :x: | :x: |
| Open-source + self-hostable | :white_check_mark: | :x: | :x: | :x: |
| Server-side registry | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Web UI | :x: | :white_check_mark: | :white_check_mark: | :white_check_mark: |

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — Copyright (c) 2025-2026 Davey Wong &lt;wgwcko@gmail.com&gt;

---

<p align="center">
  <sub>Made with ❤️ by Davey Wong</sub>
</p>
