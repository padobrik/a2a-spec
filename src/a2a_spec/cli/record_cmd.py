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
from a2a_spec.exceptions import A2ASpecError
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

    console.print("\n[bold][record][/bold] Recording snapshots...\n")
    console.print(
        "[dim]This calls live agents. Ensure adapters are configured and API keys are set.[/dim]\n"
    )

    # Load adapters from user's project
    try:
        adapters = _load_user_adapters(config)
    except Exception as e:
        console.print(f"[red]Failed to load adapters: {e}[/red]")
        console.print("\nMake sure you have adapters defined in a2a_spec/adapters/__init__.py")
        raise typer.Exit(1) from None

    if not adapters:
        console.print("[yellow]No adapters found. Create adapters first.[/yellow]")
        console.print("See: https://github.com/yourorg/a2a-spec/docs/writing-adapters.md")
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

    console.print(f"\n[done] {recorded} snapshots saved to {config.storage.path}")
    if errors:
        console.print(f"[red]WARN: {errors} recording error(s)[/red]")
        raise typer.Exit(1)


def _load_user_adapters(config: A2ASpecConfig) -> dict[str, Any]:
    """Attempt to load adapters from the user's project."""
    import importlib
    import sys

    # Add current directory to path so we can import user's adapters
    sys.path.insert(0, ".")

    try:
        mod = importlib.import_module("a2a_spec.adapters")
        adapters = getattr(mod, "ADAPTERS", {})
        return adapters
    except ImportError:
        return {}
