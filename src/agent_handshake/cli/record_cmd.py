"""handshake record — record live agent outputs as snapshots."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console

from agent_handshake.cli.exit_codes import EXIT_FAILED, EXIT_INPUT
from agent_handshake.config.loader import load_config
from agent_handshake.exceptions import HandshakeError
from agent_handshake.project import load_adapters, load_scenarios
from agent_handshake.snapshot.recorder import Recorder
from agent_handshake.snapshot.store import SnapshotStore

console = Console()


def record_command(
    suite: str | None = typer.Option(
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
    agent: Annotated[
        list[str] | None,
        typer.Option(
            "--agent",
            "-a",
            help="Record only this agent id from ADAPTERS. Repeat for several agents.",
        ),
    ] = None,
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
    for deterministic replay in CI. A scenario with an ``agents`` list is
    recorded only for those agents.
    """
    try:
        config = load_config(config_path)
    except HandshakeError as e:
        console.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(EXIT_INPUT) from None

    try:
        scenarios = load_scenarios(config, suite)
    except HandshakeError as e:
        console.print(f"[red]{e}[/red]\nRun 'handshake init' first.")
        raise typer.Exit(EXIT_INPUT) from None

    console.print("\n[bold]\\[record][/bold] Recording snapshots...\n")
    console.print(
        "[dim]This calls live agents. Ensure adapters are configured and API keys are set.[/dim]\n"
    )

    # Load adapters from user's project
    try:
        adapters = load_adapters(config)
    except Exception as e:  # noqa: BLE001  # the user's adapters package can raise anything
        console.print(f"[red]Failed to load adapters: {e}[/red]")
        raise typer.Exit(EXIT_INPUT) from None

    if not adapters:
        console.print("[yellow]No adapters found. Create adapters first.[/yellow]")
        console.print(
            "See: https://github.com/padobrik/agent-handshake/blob/main/docs/writing-adapters.md"
        )
        raise typer.Exit(EXIT_INPUT)

    unknown = sorted(set(agent or []) - set(adapters))
    if unknown:
        console.print(
            f"[red]No adapter for {', '.join(unknown)} in ADAPTERS. "
            f"Available: {', '.join(adapters)}[/red]"
        )
        raise typer.Exit(EXIT_INPUT)
    if agent:
        adapters = {k: v for k, v in adapters.items() if k in agent}

    store = SnapshotStore(config.storage.path)
    recorder = Recorder(store)

    recorded = 0
    errors = 0
    current_suite = None

    for sc in scenarios:
        if scenario and sc.name != scenario:
            continue
        if sc.suite != current_suite:
            current_suite = sc.suite
            console.print(f"  [bold]Suite: {sc.suite}[/bold]")

        for agent_id, adapter in adapters.items():
            if not sc.applies_to(agent_id):
                continue
            try:
                asyncio.run(recorder.record(adapter, sc.name, sc.input))
                console.print(f"    [green]PASS[/green] {agent_id} / {sc.name} recorded")
                recorded += 1
            except Exception as e:  # noqa: BLE001  # a failing agent is reported per scenario
                console.print(f"    [red]FAIL[/red] {agent_id} / {sc.name}: {e}")
                errors += 1

    console.print(f"\n\\[done] {recorded} snapshots saved to {config.storage.path}")
    if errors:
        console.print(f"[red]WARN: {errors} recording error(s)[/red]")
        raise typer.Exit(EXIT_FAILED)
