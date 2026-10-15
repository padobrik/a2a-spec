"""a2aspec test — run spec validation."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Annotated, Any

import typer
from rich.console import Console

from a2a_spec.config.loader import load_config
from a2a_spec.exceptions import A2ASpecError, SnapshotNotFoundError
from a2a_spec.reporting.console import print_summary, print_validation_result
from a2a_spec.reporting.github import format_github_annotation
from a2a_spec.reporting.junit import generate_junit_xml
from a2a_spec.reporting.markdown import generate_report
from a2a_spec.semantic.embeddings import EmbeddingModel
from a2a_spec.semantic.engine import SemanticEngine
from a2a_spec.snapshot.replay import ReplayEngine
from a2a_spec.snapshot.store import SnapshotStore
from a2a_spec.spec.checker import SpecChecker
from a2a_spec.spec.loader import load_spec_files

console = Console()


class OutputFormat(StrEnum):
    """Report formats for a2aspec test."""

    CONSOLE = "console"
    MARKDOWN = "markdown"
    JUNIT = "junit"
    GITHUB = "github"


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
    format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            case_sensitive=False,
            help="console; markdown or junit (report only, on stdout); "
            "github (console plus GitHub Actions annotations).",
        ),
    ] = OutputFormat.CONSOLE,
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
    # Report formats keep stdout for the report so it can be redirected.
    report_only = format in (OutputFormat.MARKDOWN, OutputFormat.JUNIT)
    out = Console(stderr=True) if report_only else console

    try:
        config = load_config(config_path)
    except A2ASpecError as e:
        out.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from None

    _specs_dir = specs_dir or config.specs_dir
    try:
        spec_files = load_spec_files(_specs_dir)
    except A2ASpecError as e:
        out.print(f"[red]Error loading specs: {e}[/red]")
        raise typer.Exit(1) from None

    if not spec_files:
        out.print("[yellow]No spec files found. Run 'a2aspec init' first.[/yellow]")
        raise typer.Exit(0)

    store = SnapshotStore(config.storage.path)
    replay_engine = ReplayEngine(store)
    semantic = semantic and config.semantic.enabled
    checker = SpecChecker(
        semantic_engine=SemanticEngine(model=EmbeddingModel(config.semantic.model))
        if semantic
        else None
    )

    records: list[dict[str, Any]] = []
    failed = 0

    mode_label = "[blue]replay[/blue]" if replay else "[yellow]live[/yellow]"
    if not report_only:
        out.print(f"\n[bold]a2a-spec[/bold] running tests ({mode_label} mode)\n")

    for spec_path, spec in spec_files:
        scenarios = store.list_scenarios(spec.producer)

        if not scenarios:
            out.print(
                f"  [yellow]WARN: No snapshots for '{spec.producer}'. "
                f"Run 'a2aspec record' first.[/yellow]"
            )
            continue

        if not report_only:
            out.print(f"  [bold]Spec: {spec.name}[/bold]")

        for scenario in scenarios:
            start = time.monotonic()
            try:
                snapshot = replay_engine.replay_snapshot(spec.producer, scenario)
            except SnapshotNotFoundError:
                out.print(f"    [yellow]WARN: {scenario}: snapshot not found[/yellow]")
                errors = ["snapshot not found"]
                passed_one = False
            else:
                try:
                    result = checker.check(spec, snapshot.output_data, snapshot.input_data)
                except ImportError as e:
                    out.print(f"[red]{e}[/red]")
                    out.print("[red]Or pass --no-semantic to skip semantic rules.[/red]")
                    raise typer.Exit(1) from None
                errors = result.failures()
                passed_one = result.passed
                if not report_only:
                    print_validation_result(
                        spec.name,
                        scenario,
                        result.structural,
                        result.policy,
                        result.semantic,
                        semantic_skipped=result.semantic_skipped,
                    )

            if not passed_one:
                failed += 1
                if format == OutputFormat.GITHUB:
                    for error in errors:
                        typer.echo(
                            format_github_annotation(
                                file=str(spec_path),
                                line=1,
                                level="error",
                                message=f"{scenario}: {error}",
                                title=f"a2a-spec {spec.name}",
                            )
                        )
            records.append(
                {
                    "spec_name": spec.name,
                    "scenario": scenario,
                    "name": scenario,
                    "passed": passed_one,
                    "errors": errors,
                    "duration_ms": (time.monotonic() - start) * 1000,
                }
            )

            if fail_fast and failed > 0:
                break

        if fail_fast and failed > 0:
            break

    if format == OutputFormat.MARKDOWN:
        typer.echo(generate_report(config.project_name, records))
    elif format == OutputFormat.JUNIT:
        typer.echo(generate_junit_xml(records, suite_name=config.project_name))
    else:
        print_summary(len(records), len(records) - failed, failed)

    if failed > 0:
        raise typer.Exit(1)
