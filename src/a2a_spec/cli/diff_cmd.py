"""a2aspec diff — compare current outputs against baselines."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from a2a_spec.config.loader import load_config
from a2a_spec.diff.engine import DiffEngine, DriftSeverity
from a2a_spec.exceptions import A2ASpecError
from a2a_spec.reporting.console import print_diff_results
from a2a_spec.snapshot.baseline import GitBaseline
from a2a_spec.snapshot.store import Snapshot, SnapshotStore

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

    'a2aspec record' overwrites snapshot files in place; this shows the
    structural and semantic differences from the version at --base, plus
    scenarios added or deleted since then.
    """
    try:
        config = load_config(config_path)
    except A2ASpecError as e:
        console.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from None

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

    try:
        baseline = GitBaseline(config.storage.path, base)
    except A2ASpecError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    console.print("\n[bold][diff][/bold] Semantic Diff Report\n")

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

            results = engine.diff(old.output_data, new.output_data, threshold)
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
