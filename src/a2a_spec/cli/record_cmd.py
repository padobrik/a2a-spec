"""a2aspec record — record live agent outputs as snapshots."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.console import Console

from a2a_spec.config.loader import load_config
from a2a_spec.config.settings import A2ASpecConfig
from a2a_spec.exceptions import A2ASpecError, ConfigError
from a2a_spec.snapshot.recorder import Recorder
from a2a_spec.snapshot.store import SnapshotStore

console = Console()


def record_command(
    suite: str = typer.Option(
        None,
        "--suite",
        "-s",
        help="Path to scenario suite YAML.",
    ),
    scenario: str | None = typer.Option(
        None,
        "--scenario",
        help="Record only a specific scenario.",
    ),
    config_path: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file.",
    ),
) -> None:
    """Record live agent outputs as snapshots.

    Calls actual agents through their adapters and saves the outputs
    as snapshot files. These snapshots are committed to git and used
    for deterministic replay in CI.
    """
    try:
        config = load_config(config_path)
    except A2ASpecError as e:
        console.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from None

    scenarios_dir = Path(config.scenarios_dir)
    if not scenarios_dir.exists():
        console.print(
            f"[red]Scenarios directory not found: {scenarios_dir}[/red]\nRun 'a2aspec init' first."
        )
        raise typer.Exit(1)

    console.print("\n[bold]\\[record][/bold] Recording snapshots...\n")
    console.print(
        "[dim]This calls live agents. Ensure adapters are configured and API keys are set.[/dim]\n"
    )

    # Load adapters from user's project
    try:
        adapters = _load_user_adapters(config)
    except Exception as e:
        console.print(f"[red]Failed to load adapters: {e}[/red]")
        raise typer.Exit(1) from None

    if not adapters:
        console.print("[yellow]No adapters found. Create adapters first.[/yellow]")
        console.print(
            "See: https://github.com/padobrik/a2a-spec/blob/main/docs/writing-adapters.md"
        )
        raise typer.Exit(1)

    store = SnapshotStore(config.storage.path)
    recorder = Recorder(store)

    # Load scenario files
    scenario_files = list(scenarios_dir.glob("*.yaml")) + list(scenarios_dir.glob("*.yml"))

    recorded = 0
    errors = 0

    for sf in scenario_files:
        raw = yaml.safe_load(sf.read_text(encoding="utf-8"))
        suite_data = raw.get("test_suite", {})
        scenarios_list = raw.get("scenarios", [])

        console.print(f"  [bold]Suite: {suite_data.get('name', sf.stem)}[/bold]")

        for sc in scenarios_list:
            sc_name = sc["name"]

            if scenario and sc_name != scenario:
                continue

            input_data = sc.get("input", {})

            for agent_id, adapter in adapters.items():
                try:
                    asyncio.run(recorder.record(adapter, sc_name, input_data))
                    console.print(f"    [green]PASS[/green] {agent_id} / {sc_name} recorded")
                    recorded += 1
                except Exception as e:
                    console.print(f"    [red]FAIL[/red] {agent_id} / {sc_name}: {e}")
                    errors += 1

    console.print(f"\n\\[done] {recorded} snapshots saved to {config.storage.path}")
    if errors:
        console.print(f"[red]WARN: {errors} recording error(s)[/red]")
        raise typer.Exit(1)


def _load_user_adapters(config: A2ASpecConfig) -> dict[str, Any]:
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
