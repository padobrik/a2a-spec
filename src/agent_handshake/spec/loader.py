"""Load and parse a2a-spec YAML files."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from a2a_spec.exceptions import ConfigError
from a2a_spec.spec.schema import Spec

logger = logging.getLogger(__name__)


def load_spec(path: str | Path) -> Spec:
    """Load a spec from a YAML file.

    Args:
        path: Path to the spec YAML file.

    Returns:
        Parsed and validated Spec object.

    Raises:
        ConfigError: If the file doesn't exist, is invalid YAML,
                     or doesn't match the spec schema.
    """
    path = Path(path)
    logger.debug("Loading spec from %s", path)

    if not path.exists():
        raise ConfigError(f"Spec file not found: {path}")

    if path.suffix not in (".yaml", ".yml"):
        raise ConfigError(f"Spec file must be .yaml or .yml: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(f"Spec file must contain a YAML mapping, got {type(raw).__name__}")

    # The spec content lives under the "spec" key
    spec_data = raw.get("spec")
    if spec_data is None:
        raise ConfigError(
            f"Spec file {path} must have a top-level 'spec' key. Got keys: {list(raw.keys())}"
        )

    try:
        spec = Spec.model_validate(spec_data)
    except ValidationError as e:
        raise ConfigError(f"Invalid spec in {path}:\n{e}") from e

    logger.info(
        "Loaded spec '%s' (producer=%s, consumer=%s)", spec.name, spec.producer, spec.consumer
    )
    return spec


def load_all_specs(directory: str | Path) -> list[Spec]:
    """Load all spec files from a directory.

    Args:
        directory: Path to directory containing spec YAML files.

    Returns:
        List of parsed Spec objects.
    """
    return [spec for _, spec in load_spec_files(directory)]


def load_spec_files(directory: str | Path) -> list[tuple[Path, Spec]]:
    """Load all spec files from a directory, keeping each file's path.

    Raises:
        ConfigError: If the directory does not exist or a spec is invalid.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise ConfigError(f"Specs directory not found: {directory}")

    paths = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))
    specs = [(path, load_spec(path)) for path in paths]
    logger.debug("Loaded %d spec(s) from %s", len(specs), directory)
    return specs
