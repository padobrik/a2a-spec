"""handshake diff — compare current outputs against baselines."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from agent_handshake.config.loader import load_config
from agent_handshake.diff.engine import DiffEngine, DriftSeverity
from agent_handshake.exceptions import HandshakeError
from agent_handshake.reporting.console import print_diff_results
from agent_handshake.snapshot.baseline import GitBaseline
from agent_handshake.snapshot.store import Snapshot, SnapshotStore

console = Console()


def diff_command(
    agent: str | None = typer.Option(
        None,
        "--agent",
        "-a",
        help="Diff only a specific agent.",
    ),
    base: str = typer.Option(
        "HEAD",
        "--base",
        "-b",
        help="Git revision holding the baseline snapshots.",
    ),
    config_path: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file.",
    ),
) -> None:
    """Compare recorded snapshots against their committed baseline.

    'handshake record' overwrites snapshot files in place; this shows the
    structural differences from the version at --base, plus
    scenarios added or deleted since then.
    """
    try:
        config = load_config(config_path)
    except HandshakeError as e:
        console.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from None

    store = SnapshotStore(config.storage.path)

    engine = DiffEngine()

    agents = [agent] if agent else store.list_agents()

    if not agents:
        console.print("[yellow]No snapshots found. Run 'handshake record' first.[/yellow]")
        raise typer.Exit(0)

    try:
        baseline = GitBaseline(config.storage.path, base)
    except HandshakeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    console.print("\n[bold]\\[diff][/bold] Diff Report\n")

    total_diffs = 0
    high_severity = 0

    for agent_id in agents:
        agent_dir = Path(config.storage.path) / agent_id
        current = sorted(agent_dir.glob("*.json")) if agent_dir.exists() else []

        for path in current:
            new = Snapshot.from_dict(json.loads(path.read_text(encoding="utf-8")))
            old = baseline.load(path)
            if old is None:
                console.print(f"  [yellow]NEW [/yellow] {agent_id} / {new.scenario}: not in {base}")
                total_diffs += 1
                continue
            if old.output_data == new.output_data:
                continue

            results = engine.diff(old.output_data, new.output_data)
            print_diff_results(agent_id, new.scenario, results)

            total_diffs += len(results)
            high_severity += sum(
                1 for r in results if r.severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL)
            )

        present = {p.resolve() for p in current}
        for path in baseline.files(agent_dir):
            if path.resolve() not in present:
                console.print(f"  [red]GONE[/red] {agent_id} / {path.name}: deleted since {base}")
                total_diffs += 1
                high_severity += 1

    console.print()
    if total_diffs == 0:
        console.print("[green]No differences detected.[/green]")
    else:
        console.print(f"{total_diffs} differences | [red]{high_severity} high/critical[/red]")

    if high_severity > 0 and config.ci.fail_on_semantic_drift:
        raise typer.Exit(2)
