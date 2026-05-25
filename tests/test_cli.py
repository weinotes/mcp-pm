"""
Tests for the CLI entry point.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from click.testing import CliRunner

from mcp_pm.cli import cli


def test_help() -> None:
    """Verify CLI help output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "mcp-pm" in result.output
    assert "Homebrew for MCP Servers" in result.output


def test_version() -> None:
    """Verify version output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    from mcp_pm import __version__
    assert __version__ in result.output


def test_install_help() -> None:
    """Verify install subcommand help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["install", "--help"])
    assert result.exit_code == 0


def test_list_help() -> None:
    """Verify list subcommand help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--help"])
    assert result.exit_code == 0


def test_search_help() -> None:
    """Verify search subcommand help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["search", "--help"])
    assert result.exit_code == 0


def test_serve_help() -> None:
    """Verify serve subcommand help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["serve", "--help"])
    assert result.exit_code == 0


def test_config_help() -> None:
    """Verify config subcommand help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["config", "--help"])
    assert result.exit_code == 0


def test_explore_help() -> None:
    """Verify explore subcommand help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["explore", "--help"])
    assert result.exit_code == 0


def test_doctor_help() -> None:
    """Verify doctor subcommand help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor", "--help"])
    assert result.exit_code == 0
