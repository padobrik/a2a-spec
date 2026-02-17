"""a2aspec pipeline — pipeline testing commands."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
import yaml
from rich.console import Console

from a2a_spec.config.loader import load_config
from a2a_spec.exceptions import A2ASpecError
from a2a_spec.pipeline.dag import build_dag
from a2a_spec.pipeline.executor import PipelineExecutor
from a2a_spec.reporting.console import print_pipeline_trace, print_summary
from a2a_spec.snapshot.replay import ReplayEngine
from a2a_spec.snapshot.store import SnapshotStore
from a2a_spec.spec.registry import SpecRegistry

console = Console()

pipeline_app = typer.Typer(
    help="Pipeline testing commands.",
    no_args_is_help=True,
)


@pipeline_app.command("test")
def pipeline_test(
    pipeline_file: str = typer.Argument(
        ...,
        help="Path to pipeline YAML file.",
    ),
    scenario: str | None = typer.Option(
        None,
        "--scenario",
        help="Run only a specific scenario.",
    ),
    mode: str = typer.Option(
        "replay",
        "--mode",
        "-m",
        help="Execution mode: replay or live.",
    ),
    config_path: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file.",
    ),
) -> None:
    """Test a pipeline definition.

    Executes the pipeline DAG in replay or live mode and validates
    each agent's output against applicable specs.
    """
    try:
        config = load_config(config_path)
    except A2ASpecError as e:
        console.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1)

    pipeline_path = Path(pipeline_file)
    if not pipeline_path.exists():
        console.print(f"[red]Pipeline file not found: {pipeline_path}[/red]")
        raise typer.Exit(1)

    raw = yaml.safe_load(pipeline_path.read_text(encoding="utf-8"))
    pipeline_spec = raw.get("pipeline", raw)

    try:
        dag = build_dag(pipeline_spec)
    except A2ASpecError as e:
        console.print(f"[red]Invalid pipeline: {e}[/red]")
        raise typer.Exit(1)

    store = SnapshotStore(config.storage.path)
    replay_engine = ReplayEngine(store)

    spec_registry: SpecRegistry | None = None
    try:
        spec_registry = SpecRegistry.from_directory(config.specs_dir)
    except A2ASpecError:
        console.print("[yellow]Could not load specs directory, skipping spec validation.[/yellow]")

    executor = PipelineExecutor(
        dag=dag,
        replay_engine=replay_engine,
        spec_registry=spec_registry,
    )

    test_cases = pipeline_spec.get("test_cases", [])
    if scenario:
        test_cases = [tc for tc in test_cases if tc["name"] == scenario]

    if not test_cases:
        console.print("[yellow]No test cases found in pipeline file.[/yellow]")
        raise typer.Exit(0)

    console.print(f"\n🧪 Pipeline test: {dag.name} ({mode} mode)\n")

    total = 0
    passed = 0
    failed = 0

    for tc in test_cases:
        total += 1
        trace = asyncio.run(
            executor.execute(
                scenario=tc["name"],
                initial_input=tc.get("input", {}),
                mode=mode,
            )
        )

        print_pipeline_trace(trace)

        if trace.passed:
            passed += 1
        else:
            failed += 1

    print_summary(total, passed, failed)

    if failed > 0:
        raise typer.Exit(1)
