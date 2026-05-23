# Changelog

Author: Davey Wong <wgwcko@gmail.com>

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Project scaffolding and initial directory structure
- All open-source standardization files (README, LICENSE, CONTRIBUTING, etc.)
- GitHub CI/CD configuration and issue/PR templates
- Project metadata and packaging configuration via `pyproject.toml`

## [0.1.0] — Planned

### Added

- `mcp install <server>` — Install an MCP server package from registry
- `mcp list` — List installed MCP servers
- `mcp search <query>` — Search for MCP servers in the registry
- `mcp explore` — Interactive TUI browser for discovering MCP servers
- `mcp serve <server>` — Start a local MCP server process
- `mcp config` — View and edit mcp-pm configuration
- `mcp sandbox <server>` — Run an MCP server in an isolated sandbox
- Registry API server (FastAPI) for server package discovery
- CLI commands with click, rich-formatted output
- YAML-based configuration file support
- Initial Python package published on PyPI

[Unreleased]: https://github.com/daveywong/mcp-pm/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/daveywong/mcp-pm/releases/tag/v0.1.0

---

*Maintained by Davey Wong &lt;wgwcko@gmail.com&gt;*
