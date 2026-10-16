"""Load project configuration from YAML."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from agent_handshake.config.settings import HandshakeConfig
from agent_handshake.exceptions import ConfigError

DEFAULT_CONFIG_NAMES = ["handshake.yaml", "handshake.yml"]
# Names from before the rename to agent-handshake, still found when no new name exists.
LEGACY_CONFIG_NAMES = ["a2a-spec.yaml", "a2a-spec.yml", "a2aspec.yaml"]
PROJECT_DIR = "handshake"
LEGACY_PROJECT_DIR = "a2a_spec"


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
        return _with_legacy_layout(HandshakeConfig())

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config: {e}") from e

    if raw is None:
        return _with_legacy_layout(HandshakeConfig())

    if not isinstance(raw, dict):
        raise ConfigError(f"Config must be a YAML mapping, got {type(raw).__name__}")

    try:
        config = HandshakeConfig.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"Invalid configuration:\n{e}") from e
    return _with_legacy_layout(config)


def _find_config() -> Path | None:
    """Search for a config file in the current directory."""
    for name in DEFAULT_CONFIG_NAMES + LEGACY_CONFIG_NAMES:
        path = Path(name)
        if path.exists():
            return path
    return None


def _with_legacy_layout(config: HandshakeConfig) -> HandshakeConfig:
    """Use ./a2a_spec/ for paths left at their defaults in a project made before the rename.

    Applies only when ./handshake/ does not exist and ./a2a_spec/ does.
    """
    if Path(PROJECT_DIR).exists() or not Path(LEGACY_PROJECT_DIR).is_dir():
        return config

    def legacy(value: str) -> str:
        return value.replace(f"./{PROJECT_DIR}/", f"./{LEGACY_PROJECT_DIR}/", 1)

    fields = ("specs_dir", "scenarios_dir", "adapters_dir")
    update: dict[str, object] = {
        f: legacy(getattr(config, f)) for f in fields if f not in config.model_fields_set
    }
    if "path" not in config.storage.model_fields_set:
        update["storage"] = config.storage.model_copy(update={"path": legacy(config.storage.path)})
    return config.model_copy(update=update)
