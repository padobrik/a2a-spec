"""All custom exceptions for agent-handshake."""

from __future__ import annotations


class HandshakeError(Exception):
    """Base exception for all agent-handshake errors."""


class ConfigError(HandshakeError):
    """Raised when configuration is invalid or missing."""
