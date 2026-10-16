"""Load project configuration from YAML."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from agent_handshake.config.settings import HandshakeConfig
from agent_handshake.exceptions import ConfigError

DEFAULT_CONFIG_NAMES = ["handshake.yaml", "handshake.yml"]


def load_config(path: str | Path | None = None) -> HandshakeConfig:
    """Load project configuration.

    If no path is given, searches for default config file names
    in the current directory.

    Args:
        path: Optional explicit path to config file.

    Returns:
        Parsed HandshakeConfig.

    Raises:
        ConfigError: If config file not found or invalid.
    """
    config_path: Path | None = Path(path) if path is not None else _find_config()

    if config_path is None:
        # Return defaults if no config file exists
        return HandshakeConfig()

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config: {e}") from e

    if raw is None:
        return HandshakeConfig()

    if not isinstance(raw, dict):
        raise ConfigError(f"Config must be a YAML mapping, got {type(raw).__name__}")

    try:
        return HandshakeConfig.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"Invalid configuration:\n{e}") from e


def _find_config() -> Path | None:
    """Search for a config file in the current directory."""
    for name in DEFAULT_CONFIG_NAMES:
        path = Path(name)
        if path.exists():
            return path
    return None
