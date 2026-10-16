"""Load project configuration from YAML."""

from __future__ import annotations

import difflib
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from agent_handshake.config.settings import HandshakeConfig
from agent_handshake.exceptions import ConfigError
from agent_handshake.spec.removed import REMOVED_IN

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

    problem = _removed_setting(raw) or _unknown_setting(raw, HandshakeConfig)
    if problem is not None:
        raise ConfigError(f"{config_path}: {problem}")

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


def _removed_setting(raw: dict[str, object]) -> str | None:
    """The migration message for a setting that was removed, or None."""
    if "semantic" in raw:
        return (
            f"Setting 'semantic' was removed in {REMOVED_IN} with semantic rules. "
            "Delete it. See CHANGELOG.md."
        )
    ci = raw.get("ci")
    for key in ("fail_on_semantic_drift", "drift_threshold"):
        if isinstance(ci, dict) and key in ci:
            return (
                f"Setting 'ci.{key}' was removed in {REMOVED_IN}; handshake diff fails on "
                "high-severity drift. Delete it. See CHANGELOG.md."
            )
    return None


def _unknown_setting(
    raw: dict[str, object], model: type[BaseModel], prefix: str = ""
) -> str | None:
    """A message for the first key the model does not know, with the closest known key."""
    known = list(model.model_fields)
    for key, value in raw.items():
        if key not in known:
            close = difflib.get_close_matches(str(key), known, n=1)
            hint = f" Did you mean '{prefix}{close[0]}'?" if close else ""
            where = f" in '{prefix[:-1]}'" if prefix else ""
            return (
                f"Unknown setting '{prefix}{key}'.{hint} Known settings{where}: {', '.join(known)}."
            )
        annotation = model.model_fields[key].annotation
        if (
            isinstance(value, dict)
            and isinstance(annotation, type)
            and issubclass(annotation, BaseModel)
        ):
            nested = _unknown_setting(value, annotation, f"{prefix}{key}.")
            if nested is not None:
                return nested
    return None
