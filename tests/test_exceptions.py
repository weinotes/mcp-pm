"""
Tests for the mcp-pm exception hierarchy.

Verifies inheritance, raise/catch patterns, message propagation,
and isinstance checks for all custom exception types.

Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
Author: Davey Wong <wgwcko@gmail.com> (https://www.guangweiblog.com)
Licensed under MIT License.
"""

from __future__ import annotations

import pytest

from mcp_pm.exceptions import (
    ClientError,
    ConfigError,
    InstallError,
    McpPmError,
    RegistryError,
    SandboxError,
)

# ── All custom exceptions ─────────────────────────────────────────────────

ALL_EXCEPTIONS = [
    RegistryError,
    InstallError,
    ClientError,
    ConfigError,
    SandboxError,
]


# ── Inheritance ───────────────────────────────────────────────────────────


class TestInheritance:
    """Every custom exception inherits from McpPmError (and thus Exception)."""

    def test_base_is_exception(self) -> None:
        """McpPmError itself inherits from Exception."""
        assert issubclass(McpPmError, Exception)

    def test_all_inherit_mcp_pm_error(self) -> None:
        """Every custom exception is a subclass of McpPmError."""
        for exc_cls in ALL_EXCEPTIONS:
            assert issubclass(exc_cls, McpPmError), f"{exc_cls.__name__} does not inherit McpPmError"

    def test_all_inherit_exception(self) -> None:
        """Every custom exception is a subclass of Exception (transitive)."""
        for exc_cls in ALL_EXCEPTIONS:
            assert issubclass(exc_cls, Exception), f"{exc_cls.__name__} does not inherit Exception"


# ── Instantiation and message ────────────────────────────────────────────


class TestInstantiation:
    """Exceptions can be constructed with or without a message."""

    @pytest.mark.parametrize("exc_cls", ALL_EXCEPTIONS)
    def test_default_message(self, exc_cls: type[McpPmError]) -> None:
        """Constructed without arguments produces an empty message."""
        exc = exc_cls()
        assert str(exc) == ""

    @pytest.mark.parametrize("exc_cls", ALL_EXCEPTIONS)
    def test_custom_message(self, exc_cls: type[McpPmError]) -> None:
        """Constructed with a string preserves the message."""
        msg = f"Test {exc_cls.__name__} error"
        exc = exc_cls(msg)
        assert str(exc) == msg
        assert exc.args[0] == msg

    @pytest.mark.parametrize("exc_cls", ALL_EXCEPTIONS)
    def test_multiple_args(self, exc_cls: type[McpPmError]) -> None:
        """Constructed with multiple positional args stores them all."""
        exc = exc_cls("first", "second", 42)
        assert exc.args == ("first", "second", 42)


# ── Raise / Catch ────────────────────────────────────────────────────────


class TestRaiseAndCatch:
    """All exceptions can be raised and caught by their own type."""

    @pytest.mark.parametrize("exc_cls", ALL_EXCEPTIONS)
    def test_catch_by_own_type(self, exc_cls: type[McpPmError]) -> None:
        """Catching by exact exception type works."""
        with pytest.raises(exc_cls):
            raise exc_cls(f"Catch me by {exc_cls.__name__}")

    @pytest.mark.parametrize("exc_cls", ALL_EXCEPTIONS)
    def test_catch_by_base(self, exc_cls: type[McpPmError]) -> None:
        """Catching by base McpPmError catches any custom exception."""
        with pytest.raises(McpPmError):
            raise exc_cls("caught by base")

    @pytest.mark.parametrize("exc_cls", ALL_EXCEPTIONS)
    def test_catch_by_exception(self, exc_cls: type[McpPmError]) -> None:
        """Catching by built-in Exception catches any custom exception."""
        with pytest.raises(Exception):
            raise exc_cls("caught by Exception")

    @pytest.mark.parametrize("exc_cls", ALL_EXCEPTIONS)
    def test_message_preserved_on_catch(self, exc_cls: type[McpPmError]) -> None:
        """The original message is preserved when caught."""
        msg = f"Preserve this: {exc_cls.__name__}"
        try:
            raise exc_cls(msg)
        except exc_cls as e:
            assert str(e) == msg
        except McpPmError as e:
            assert str(e) == msg


# ── isinstance checks ────────────────────────────────────────────────────


class TestIsInstance:
    """isinstance works correctly for the exception hierarchy."""

    def test_instance_of_own_type(self) -> None:
        """An exception instance checks as its own type."""
        for exc_cls in ALL_EXCEPTIONS:
            exc = exc_cls()
            assert isinstance(exc, exc_cls), f"{exc_cls.__name__} instance not isinstance of itself"

    def test_instance_of_base(self) -> None:
        """Every custom exception instance checks as McpPmError."""
        for exc_cls in ALL_EXCEPTIONS:
            exc = exc_cls()
            assert isinstance(exc, McpPmError), f"{exc_cls.__name__} instance not isinstance of McpPmError"

    def test_instance_of_exception(self) -> None:
        """Every custom exception instance checks as Exception."""
        for exc_cls in ALL_EXCEPTIONS:
            exc = exc_cls()
            assert isinstance(exc, Exception), f"{exc_cls.__name__} instance not isinstance of Exception"

    def test_not_instance_of_sibling(self) -> None:
        """An exception is NOT isinstance of a sibling type."""
        for exc_cls in ALL_EXCEPTIONS:
            for sibling in ALL_EXCEPTIONS:
                if sibling is exc_cls:
                    continue
                exc = exc_cls()
                assert not isinstance(exc, sibling), (
                    f"{exc_cls.__name__} should not be isinstance of {sibling.__name__}"
                )


# ── Try / except flow ────────────────────────────────────────────────────


class TestExceptFlow:
    """Practical try/except blocks work end-to-end."""

    def test_catch_specific_first(self) -> None:
        """Catching specific exceptions before broader ones works."""
        try:
            raise RegistryError("registry unavailable")
        except RegistryError:
            pass
        except McpPmError:
            pytest.fail("Should have been caught by RegistryError")

    def test_catch_base_fallback(self) -> None:
        """Catching McpPmError as fallback works for any custom exception."""
        cases = [
            (InstallError, "install failed"),
            (ClientError, "client timeout"),
            (ConfigError, "bad config"),
            (SandboxError, "sandbox crash"),
        ]
        for exc_cls, msg in cases:
            try:
                raise exc_cls(msg)
            except McpPmError as e:
                assert str(e) == msg

    def test_raise_with_cause(self) -> None:
        """Exception chaining works (raise ... from ...)."""
        cause = ValueError("underlying cause")
        with pytest.raises(RegistryError) as exc_info:
            raise RegistryError("wrapped") from cause
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert str(exc_info.value.__cause__) == "underlying cause"
