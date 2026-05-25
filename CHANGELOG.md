# Changelog

Author: Davey Wong <wgwcko@gmail.com>

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] — 2026-06-19

### Added

- **6 new source types** — now supports install via uvx, npx, go, cargo, deno, and brew (in addition to git, pip, npm)
- **SourceType enum** expanded to 10 members — each with dedicated install/update methods
- **`_extract_version_from_stdout()`** shared helper for version parsing across pip, uvx, and npx outputs
- **Auto-detection** in `mcp-pm install` — CLI auto-detects uvx/npx/go/cargo/deno/brew from URL prefix

### Changed

- **Version bump** — 0.2.1 → 0.3.0 (minor: new install source types)

## [0.2.1] — 2026-06-19

### Fixed

- **P0: FormulaManager CRUD path inconsistency** — `save()`, `load()`, `delete()` now use `self.install_dir` instead of hardcoded `~/.mcp-pm/servers/`
- **P2: Health endpoint version hardcoded** — `/health` returns `"0.2.1"` (was `"0.1.0"`)
- **Copyright headers** — Added to `webui/lang.py`

### Added

- **255 production-grade unit tests** (up from 28), covering formula, installer, tap, client, server, exceptions
- **Coverage 22% → 43%** — core modules at 77-96%
- **Deduplicated `.gitignore`** — 57 unique entries, added `.mcp-pm/`

### Changed

- **Version bump** — 0.2.0 → 0.2.1 (SemVer patch for bugfixes)

## [0.2.0] — 2026-05-25

### Added

- 10 new Homebrew-equivalent commands: `pin`/`unpin`, `services` (list/start/stop/restart), `create`, `bump`, `reinstall`, `deps` (`--tree`), `leaves`, `autoremove`, `home`, `log` (`--follow`)
- 28 CLI commands total (up from 18)

### Changed

- Split `cli.py` (1384 lines → 50 lines) into modular `cmd/` package with 29 files
- Monolith resolved: each command in its own file under `cmd/_*.py`
- `test_version` now dynamically reads `__version__` instead of hardcoding

### Fixed

- Ruff lint issues in new cmd files

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

[Unreleased]: https://github.com/weinotes/mcp-pm/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/weinotes/mcp-pm/releases/tag/v0.3.0
[0.2.1]: https://github.com/weinotes/mcp-pm/releases/tag/v0.2.1
[0.2.0]: https://github.com/weinotes/mcp-pm/releases/tag/v0.2.0
[0.1.1]: https://github.com/weinotes/mcp-pm/releases/tag/v0.1.1
[0.1.0]: https://github.com/weinotes/mcp-pm/releases/tag/v0.1.0

---

*Maintained by Davey Wong &lt;wgwcko@gmail.com&gt;*
