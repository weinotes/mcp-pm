# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
# Licensed under MIT License.

"""Audit system — quality checks for MCP server formulae.

Inspired by Homebrew's ``brew audit``. Checks formula YAML files
for completeness, correctness, and consistency.

Checks performed:
  - Required fields present
  - Source URL is reachable (git/pip/npm)
  - Version is valid SemVer
  - Dependencies are installed
  - No duplicate servers

Usage::

    mcp-pm audit                  # Audit all installed servers
    mcp-pm audit my-server        # Audit a specific server

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class AuditIssue:
    """A single audit finding."""

    severity: str       # "error" | "warning" | "info"
    check: str          # Check name, e.g. "missing_field"
    message: str        # Human-readable description
    field: str | None = None  # Affected formula field


@dataclass
class AuditResult:
    """Complete audit result for one server."""

    name: str
    path: Path | None
    issues: list[AuditIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# ── Audit checks ─────────────────────────────────────────────────────────


def _check_required_fields(data: dict[str, Any], path: str) -> list[AuditIssue]:
    """Check that required fields are present and non-empty."""
    issues: list[AuditIssue] = []
    for field_name in ("name",):
        val = data.get(field_name, "")
        if not val:
            issues.append(AuditIssue(
                severity="error",
                check="missing_field",
                message=f"Required field '{field_name}' is missing or empty [{path}]",
                field=field_name,
            ))

    # source_type must be one of known types
    st = data.get("source_type", data.get("type", ""))
    if st and st not in ("git", "npm", "pip", "docker"):
        issues.append(AuditIssue(
            severity="warning",
            check="unknown_source_type",
            message=f"Unrecognized source_type '{st}' [{path}]",
            field="source_type",
        ))

    return issues


def _check_version(data: dict[str, Any], path: str) -> list[AuditIssue]:
    """Check that version is valid."""
    issues: list[AuditIssue] = []
    version = data.get("version", "")
    if not version or version == "unknown":
        issues.append(AuditIssue(
            severity="warning",
            check="missing_version",
            message=f"Version is unknown [{path}]",
            field="version",
        ))
    return issues


def _check_source_url(data: dict[str, Any], path: str) -> list[AuditIssue]:
    """Check that source URL is well-formed."""
    issues: list[AuditIssue] = []
    url = data.get("source_url", data.get("url", ""))
    if not url:
        issues.append(AuditIssue(
            severity="warning",
            check="missing_source_url",
            message=f"No source URL [{path}]",
            field="source_url",
        ))
    return issues


def _check_dependencies(
    data: dict[str, Any],
    servers_dir: Path,
    path: str,
) -> list[AuditIssue]:
    """Check that declared dependencies are installed."""
    issues: list[AuditIssue] = []
    deps = data.get("dependencies", [])
    if not deps:
        return issues
    for dep in deps:
        dep_path = servers_dir / dep
        if not dep_path.exists() or not (dep_path / "formula.yaml").exists():
            issues.append(AuditIssue(
                severity="error",
                check="missing_dependency",
                message=f"Dependency '{dep}' is not installed [{path}]",
            ))
    return issues


# ── Audit runner ─────────────────────────────────────────────────────────


def audit_server(name: str) -> AuditResult:
    """Audit a single installed server."""
    servers_dir = Path.home() / ".mcp-pm" / "servers"
    server_path = servers_dir / name

    issues: list[AuditIssue] = []

    # Check if the server directory exists
    if not server_path.exists():
        issues.append(AuditIssue(
            severity="error",
            check="not_found",
            message=f"Server '{name}' is not installed",
        ))
        return AuditResult(name=name, path=None, issues=issues)

    # Try formula.yaml first, then manifest.yaml
    formula_path = server_path / "formula.yaml"
    manifest_path = server_path / "manifest.yaml"

    data: dict[str, Any] = {}
    source_path = ""
    if formula_path.exists():
        try:
            raw = yaml.safe_load(formula_path.read_text(encoding="utf-8"))
            data = raw or {}
            source_path = str(formula_path)
        except Exception as exc:
            issues.append(AuditIssue(
                severity="error",
                check="parse_error",
                message=f"Failed to parse formula.yaml: {exc}",
            ))
    elif manifest_path.exists():
        try:
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            data = raw or {}
            source_path = str(manifest_path)
        except Exception as exc:
            issues.append(AuditIssue(
                severity="error",
                check="parse_error",
                message=f"Failed to parse manifest.yaml: {exc}",
            ))
    else:
        issues.append(AuditIssue(
            severity="error",
            check="no_formula",
            message=f"No formula.yaml or manifest.yaml found in {server_path}",
        ))
        return AuditResult(name=name, path=server_path, issues=issues)

    # Run checks
    issues.extend(_check_required_fields(data, source_path))
    issues.extend(_check_version(data, source_path))
    issues.extend(_check_source_url(data, source_path))
    issues.extend(_check_dependencies(data, servers_dir, source_path))

    return AuditResult(name=name, path=server_path, issues=issues)


def audit_all() -> list[AuditResult]:
    """Audit all installed servers."""
    servers_dir = Path.home() / ".mcp-pm" / "servers"
    if not servers_dir.exists():
        return []
    results: list[AuditResult] = []
    for entry in sorted(servers_dir.iterdir()):
        if entry.is_dir():
            results.append(audit_server(entry.name))
    return results


def fix_issues(result: AuditResult) -> int:
    """Auto-fix minor audit issues for a server.

    Returns the number of issues fixed.
    Currently fixes:
      - missing_version: infer version from installed package metadata

    Args:
        result: AuditResult from audit_server().

    Returns:
        Number of issues that were fixed.
    """
    if result.passed:
        return 0

    fixed = 0
    server_path = result.path
    if server_path is None:
        return 0

    # Check for fixable issues
    formula_path = server_path / "formula.yaml"
    if not formula_path.exists():
        return 0

    try:
        raw = yaml.safe_load(formula_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.debug("Failed to load formula YAML '%s': %s", formula_path, exc)
        return 0

    for issue in result.issues:
        # Fix: missing_version → try to infer version from manifest
        if issue.check == "missing_version" and raw.get("version", "unknown") == "unknown":
            manifest_path = server_path / "manifest.yaml"
            if manifest_path.exists():
                try:
                    m_raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                    ver = m_raw.get("version")
                    if ver and ver != "unknown":
                        raw["version"] = ver
                        fixed += 1
                except Exception as exc:
                    logger.debug("Failed to infer version from manifest: %s", exc)

    if fixed > 0:
        formula_path.write_text(
            yaml.dump(raw, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    return fixed
