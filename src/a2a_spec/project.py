"""Load the user's project: adapters and scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from a2a_spec.config.settings import A2ASpecConfig
from a2a_spec.exceptions import ConfigError


@dataclass(frozen=True)
class Scenario:
    """One named input from a scenario file."""

    suite: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)


def load_scenarios(config: A2ASpecConfig, suite: str | None = None) -> list[Scenario]:
    """Load scenarios from ``scenarios_dir``, or from one ``suite`` file.

    Raises:
        ConfigError: If the directory or file is missing or not valid YAML.
    """
    if suite is not None:
        files = [Path(suite)]
        if not files[0].exists():
            raise ConfigError(f"Scenario suite not found: {suite}")
    else:
        directory = Path(config.scenarios_dir)
        if not directory.exists():
            raise ConfigError(f"Scenarios directory not found: {directory}")
        files = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))

    scenarios: list[Scenario] = []
    for path in files:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {path}: {e}") from e
        suite_name = (raw.get("test_suite") or {}).get("name", path.stem)
        for item in raw.get("scenarios") or []:
            scenarios.append(Scenario(suite_name, item["name"], item.get("input") or {}))
    return scenarios


def load_adapters(config: A2ASpecConfig) -> dict[str, Any]:
    """Load the ADAPTERS mapping from the project's adapters package.

    The package is loaded from its file path under a private module name:
    importing it as ``a2a_spec.adapters`` would resolve to this library's
    own subpackage, because the project directory shares the library's name.

    Raises:
        ConfigError: If the package is missing or does not define ADAPTERS.
    """
    import hashlib
    import importlib.util
    import sys

    package_dir = Path(config.adapters_dir).resolve()
    init_file = package_dir / "__init__.py"
    if not init_file.exists():
        raise ConfigError(
            f"No adapters package at {init_file}. Define ADAPTERS = {{agent_id: adapter}} there."
        )

    # Let adapters import the user's own modules relative to the project root.
    if "" not in sys.path and str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))

    name = "_a2a_spec_project_adapters_" + hashlib.sha1(str(package_dir).encode()).hexdigest()[:8]
    spec = importlib.util.spec_from_file_location(
        name, init_file, submodule_search_locations=[str(package_dir)]
    )
    if spec is None or spec.loader is None:
        raise ConfigError(f"Cannot load adapters from {init_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise

    adapters = getattr(module, "ADAPTERS", None)
    if not isinstance(adapters, dict):
        raise ConfigError(f"{init_file} must define ADAPTERS as a dict of agent_id -> adapter")
    return adapters
