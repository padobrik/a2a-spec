"""a2aspec diff — compare current outputs against baselines."""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from a2a_spec.config.loader import load_config
from a2a_spec.diff.engine import DiffEngine, DriftSeverity
from a2a_spec.exceptions import A2ASpecError
from a2a_spec.reporting.console import print_diff_results
from a2a_spec.snapshot.store import SnapshotStore

console = Console()


def diff_command(
    agent: str | None = typer.Option(
        None,
        "--agent",
        "-a",
        help="Diff only a specific agent.",
    ),
    threshold: float = typer.Option(
        0.85,
        "--threshold",
        "-t",
        help="Semantic similarity threshold.",
    ),
    config_path: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file.",
    ),
) -> None:
    """Compare current snapshots against baselines.

    Shows structural and semantic differences between the most recent
    recording and the previous baseline.
    """
    try:
        config = load_config(config_path)
    except A2ASpecError as e:
        console.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1)

    store = SnapshotStore(config.storage.path)

    semantic_model = None
    if config.semantic.enabled:
        try:
            from a2a_spec.semantic.embeddings import EmbeddingModel

            semantic_model = EmbeddingModel(config.semantic.model)
        except ImportError:
            console.print(
                "[yellow]sentence-transformers not installed. "
                "Using token overlap for comparison. "
                "Install with: pip install a2a-spec\\[semantic][/yellow]\n"
            )

    engine = DiffEngine(semantic_model=semantic_model)

    agents = [agent] if agent else store.list_agents()

    if not agents:
        console.print("[yellow]No snapshots found. Run 'a2aspec record' first.[/yellow]")
        raise typer.Exit(0)

    console.print("\n🔍 Semantic Diff Report\n")

    total_diffs = 0
    high_severity = 0

    for agent_id in agents:
        snapshots = store.load_all(agent_id)

        by_scenario: dict[str, list[Any]] = {}
        for snap in snapshots:
            by_scenario.setdefault(snap.scenario, []).append(snap)

        for scenario, snaps in sorted(by_scenario.items()):
            if len(snaps) < 2:
                continue

            old = snaps[-2]
            new = snaps[-1]

            results = engine.diff(old.output_data, new.output_data, threshold)
            print_diff_results(agent_id, scenario, results)

            total_diffs += len(results)
            high_severity += sum(
                1 for r in results if r.severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL)
            )

    console.print()
    if total_diffs == 0:
        console.print("[green]No differences detected.[/green]")
    else:
        console.print(f"{total_diffs} differences | [red]{high_severity} high/critical[/red]")

    if high_severity > 0 and config.ci.fail_on_semantic_drift:
        raise typer.Exit(2)
