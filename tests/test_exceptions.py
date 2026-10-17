"""Tests for all custom exception types."""

from __future__ import annotations

from agent_handshake.exceptions import (
    ConfigError,
)


class TestConfigError:
    """Tests for ConfigError."""

    def test_is_agent_handshake_error(self) -> None:
        """ConfigError must inherit from HandshakeError."""
        from agent_handshake.exceptions import HandshakeError

        err = ConfigError("bad config")
        assert isinstance(err, HandshakeError)

    def test_message_preserved(self) -> None:
        """The message must be accessible."""
        err = ConfigError("field 'x' is required")
        assert "field 'x' is required" in str(err)


class TestExceptionHierarchy:
    """Tests for the exception hierarchy."""

    def test_all_errors_inherit_base(self) -> None:
        """All custom exceptions must inherit from HandshakeError."""
        from agent_handshake.exceptions import HandshakeError

        errors = [
            ConfigError("msg"),
        ]
        for err in errors:
            assert isinstance(err, HandshakeError), (
                f"{type(err).__name__} must extend HandshakeError"
            )
