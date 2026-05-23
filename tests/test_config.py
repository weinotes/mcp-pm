"""
Tests for configuration management.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from pathlib import Path

from mcp_pm.config import Config


def test_config_load_nonexistent(tmp_path: Path) -> None:
    """Loading non-existent config returns empty dict."""
    config_path = tmp_path / ".mcp-pm" / "config.yaml"
    cfg = Config(config_path)
    data = cfg.load()
    assert data == {}


def test_config_save_and_load(tmp_path: Path) -> None:
    """Round-trip save and load preserves values."""
    config_path = tmp_path / ".mcp-pm" / "config.yaml"
    cfg = Config(config_path)
    cfg.set("registry.url", "https://mcp.so/api")
    cfg.set("sandbox.level", "subprocess")
    cfg.save()

    cfg2 = Config(config_path)
    cfg2.load()
    assert cfg2.get("registry.url") == "https://mcp.so/api"
    assert cfg2.get("sandbox.level") == "subprocess"


def test_config_get_default(tmp_path: Path) -> None:
    """Getting non-existent key returns default."""
    cfg = Config(tmp_path / "nonexistent.yaml")
    cfg.load()
    assert cfg.get("missing.key", "default") == "default"


def test_config_export_import(tmp_path: Path) -> None:
    """Export and import preserve structure."""
    cfg = Config(tmp_path / "config.yaml")
    cfg.set("registry.url", "https://mcp.so")
    exported = cfg.export()

    cfg2 = Config(tmp_path / "config2.yaml")
    cfg2.import_str(exported)
    assert cfg2.get("registry.url") == "https://mcp.so"
