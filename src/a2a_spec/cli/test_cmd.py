"""a2aspec test — run spec validation."""

from __future__ import annotations

import typer
from rich.console import Console

from a2a_spec.config.loader import load_config
from a2a_spec.exceptions import A2ASpecError, SnapshotNotFoundError
from a2a_spec.reporting.console import print_summary, print_validation_result
from a2a_spec.semantic.embeddings import EmbeddingModel
from a2a_spec.semantic.engine import SemanticEngine
from a2a_spec.snapshot.replay import ReplayEngine
from a2a_spec.snapshot.store import SnapshotStore
from a2a_spec.spec.checker import SpecChecker
from a2a_spec.spec.loader import load_all_specs

console = Console()


def test_command(
    replay: bool = typer.Option(
        True,
        "--replay/--live",
        help="Use recorded snapshots (replay) or call live agents.",
    ),
    specs_dir: str | None = typer.Option(
        None,
        "--specs",
        "-s",
        help="Path to specs directory.",
    ),
    config_path: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file.",
    ),
    format: str = typer.Option(
        "console",
        "--format",
        "-f",
        help="Output format: console, markdown, junit",
    ),
    fail_fast: bool = typer.Option(
        False,
        "--fail-fast",
        help="Stop on first failure.",
    ),
    semantic: bool = typer.Option(
        True,
        "--semantic/--no-semantic",
        help="Evaluate semantic rules (requires the 'semantic' extra).",
    ),
) -> None:
    """Run spec validation against recorded snapshots or live agents.

    In replay mode (default), no LLM calls are made. Outputs are loaded
    from stored snapshots and validated against specs.
    """
    try:
        config = load_config(config_path)
    except A2ASpecError as e:
        console.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from None

    _specs_dir = specs_dir or config.specs_dir
    try:
        specs = load_all_specs(_specs_dir)
    except A2ASpecError as e:
        console.print(f"[red]Error loading specs: {e}[/red]")
        raise typer.Exit(1) from None

    if not specs:
        console.print("[yellow]No spec files found. Run 'a2aspec init' first.[/yellow]")
        raise typer.Exit(0)

    store = SnapshotStore(config.storage.path)
    replay_engine = ReplayEngine(store)
    semantic = semantic and config.semantic.enabled
    checker = SpecChecker(
        semantic_engine=SemanticEngine(model=EmbeddingModel(config.semantic.model))
        if semantic
        else None
    )

    total = 0
    passed = 0
    failed = 0

    mode_label = "[blue]replay[/blue]" if replay else "[yellow]live[/yellow]"
    console.print(f"\n[bold]a2a-spec[/bold] running tests ({mode_label} mode)\n")

    for spec in specs:
        scenarios = store.list_scenarios(spec.producer)

        if not scenarios:
            console.print(
                f"  [yellow]WARN: No snapshots for '{spec.producer}'. "
                f"Run 'a2aspec record' first.[/yellow]"
            )
            continue

        console.print(f"  [bold]Spec: {spec.name}[/bold]")

        for scenario in scenarios:
            total += 1

            try:
                snapshot = replay_engine.replay_snapshot(spec.producer, scenario)
            except SnapshotNotFoundError:
                console.print(f"    [yellow]WARN: {scenario}: snapshot not found[/yellow]")
                failed += 1
                continue

            try:
                result = checker.check(spec, snapshot.output_data, snapshot.input_data)
            except ImportError as e:
                console.print(f"[red]{e}[/red]")
                console.print("[red]Or pass --no-semantic to skip semantic rules.[/red]")
                raise typer.Exit(1) from None

            if result.passed:
                passed += 1
            else:
                failed += 1

            print_validation_result(
                spec.name,
                scenario,
                result.structural,
                result.policy,
                result.semantic,
                semantic_skipped=result.semantic_skipped,
            )

            if fail_fast and failed > 0:
                break

        if fail_fast and failed > 0:
            break

    print_summary(total, passed, failed)

    if failed > 0:
        raise typer.Exit(1)
