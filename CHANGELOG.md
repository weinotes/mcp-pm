# Changelog

Author: Davey Wong <wgwcko@gmail.com>

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] — 2026-05-25

### Fixed

- Fix `pyproject.toml` `[tool.setuptools.package_data]` → `[tool.setuptools.package-data]` for compatibility with setuptools ≥70
- Remove dead ruff per-file-ignore entry for `registry.py` (file split to `registry/` directory)
- Add `logger.debug()` to 14 `except Exception` blocks across 8 files — eliminate silent exception swallowing
- Fix `tap.py` undefined variable `path` in exception handler (should be loop var `f`)
- Suppress `MockProcess.wait` coroutine warning in sandbox test

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

[Unreleased]: https://github.com/weinotes/mcp-pm/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/weinotes/mcp-pm/releases/tag/v0.1.1
[0.1.0]: https://github.com/weinotes/mcp-pm/releases/tag/v0.1.0

---

*Maintained by Davey Wong &lt;wgwcko@gmail.com&gt;*
