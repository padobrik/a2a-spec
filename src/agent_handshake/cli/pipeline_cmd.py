"""handshake pipeline — pipeline testing commands."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from rich.console import Console

from agent_handshake.config.loader import load_config
from agent_handshake.exceptions import HandshakeError, PipelineExecutionError
from agent_handshake.pipeline.dag import build_dag
from agent_handshake.pipeline.executor import PipelineExecutor
from agent_handshake.project import load_adapters
from agent_handshake.reporting.console import print_pipeline_trace, print_summary
from agent_handshake.semantic.embeddings import EmbeddingModel
from agent_handshake.semantic.engine import SemanticEngine
from agent_handshake.snapshot.replay import ReplayEngine
from agent_handshake.snapshot.store import SnapshotStore
from agent_handshake.spec.checker import SpecChecker
from agent_handshake.spec.registry import SpecRegistry

console = Console()


class Mode(StrEnum):
    """Pipeline execution modes."""

    REPLAY = "replay"
    LIVE = "live"


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
    mode: Annotated[
        Mode,
        typer.Option(
            "--mode",
            "-m",
            case_sensitive=False,
            help="replay: use snapshots; live: call the agents in ADAPTERS.",
        ),
    ] = Mode.REPLAY,
    config_path: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file.",
    ),
    semantic: bool = typer.Option(
        True,
        "--semantic/--no-semantic",
        help="Evaluate semantic rules (requires the 'semantic' extra).",
    ),
) -> None:
    """Test a pipeline definition.

    Executes the pipeline DAG in replay or live mode and checks each
    agent's output against the structural, policy and semantic rules of
    the specs where that agent is the producer.
    """
    try:
        config = load_config(config_path)
    except HandshakeError as e:
        console.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from None

    pipeline_path = Path(pipeline_file)
    if not pipeline_path.exists():
        console.print(f"[red]Pipeline file not found: {pipeline_path}[/red]")
        raise typer.Exit(1)

    raw = yaml.safe_load(pipeline_path.read_text(encoding="utf-8"))
    pipeline_spec = raw.get("pipeline", raw)

    try:
        dag = build_dag(pipeline_spec)
    except HandshakeError as e:
        console.print(f"[red]Invalid pipeline: {e}[/red]")
        raise typer.Exit(1) from None

    store = SnapshotStore(config.storage.path)
    replay_engine = ReplayEngine(store)

    spec_registry: SpecRegistry | None = None
    try:
        spec_registry = SpecRegistry.from_directory(config.specs_dir)
    except HandshakeError:
        console.print("[yellow]Could not load specs directory, skipping spec validation.[/yellow]")

    adapters: dict[str, Any] = {}
    if mode == Mode.LIVE:
        try:
            adapters = load_adapters(config)
        except Exception as e:
            console.print(f"[red]Cannot run live: {e}[/red]")
            raise typer.Exit(1) from None

    semantic = semantic and config.semantic.enabled
    checker = SpecChecker(
        semantic_engine=SemanticEngine(model=EmbeddingModel(config.semantic.model))
        if semantic
        else None
    )
    executor = PipelineExecutor(
        dag=dag,
        replay_engine=replay_engine,
        adapters=adapters,
        spec_registry=spec_registry,
        checker=checker,
    )

    test_cases = pipeline_spec.get("test_cases", [])
    if scenario:
        test_cases = [tc for tc in test_cases if tc["name"] == scenario]

    if not test_cases:
        console.print("[yellow]No test cases found in pipeline file.[/yellow]")
        raise typer.Exit(0)

    console.print(f"\n[bold]\\[test][/bold] Pipeline: {dag.name} ({mode.value} mode)\n")

    total = 0
    passed = 0
    failed = 0

    for tc in test_cases:
        total += 1
        try:
            trace = asyncio.run(
                executor.execute(
                    scenario=tc["name"],
                    initial_input=tc.get("input", {}),
                    mode=mode.value,
                )
            )
        except PipelineExecutionError as e:
            console.print(f"\n  [red]FAIL[/red] Pipeline: {dag.name} / {tc['name']}: {e}")
            failed += 1
            continue
        except ImportError as e:
            console.print(f"[red]{e}[/red]")
            console.print("[red]Or pass --no-semantic to skip semantic rules.[/red]")
            raise typer.Exit(1) from None

        print_pipeline_trace(trace)

        if trace.passed:
            passed += 1
        else:
            failed += 1

    print_summary(total, passed, failed)

    if failed > 0:
        raise typer.Exit(1)
