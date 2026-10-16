"""handshake test — run spec validation."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from agent_handshake.config.loader import load_config
from agent_handshake.exceptions import ConfigError, HandshakeError, SnapshotNotFoundError
from agent_handshake.project import Scenario, load_adapters, load_scenarios
from agent_handshake.reporting.console import print_summary, print_validation_result
from agent_handshake.reporting.github import format_github_annotation
from agent_handshake.reporting.junit import generate_junit_xml
from agent_handshake.reporting.markdown import generate_report
from agent_handshake.snapshot.replay import ReplayEngine
from agent_handshake.snapshot.store import SnapshotStore
from agent_handshake.spec.checker import SpecChecker
from agent_handshake.spec.loader import load_spec_files
from agent_handshake.spec.schema import Spec

console = Console()


@dataclass(frozen=True)
class Case:
    """One producer output to check, or the reason there is none."""

    scenario: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None
    expected: dict[str, Any] | None = None


class OutputFormat(StrEnum):
    """Report formats for handshake test."""

    CONSOLE = "console"
    MARKDOWN = "markdown"
    JUNIT = "junit"
    GITHUB = "github"


def test_command(
    replay: bool = typer.Option(
        True,
        "--replay/--live",
        help="Check recorded snapshots (replay), or call the producers in ADAPTERS "
        "with every scenario and check their live output (nothing is saved).",
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
) -> None:
    """Run spec validation against recorded snapshots or live agents.

    In replay mode (default), no LLM calls are made. Outputs are loaded
    from stored snapshots and validated against specs. In live mode each
    spec's producer is called through its adapter for every scenario.
    """
    # Report formats keep stdout for the report so it can be redirected.
    report_only = format in (OutputFormat.MARKDOWN, OutputFormat.JUNIT)
    out = Console(stderr=True) if report_only else console

    try:
        config = load_config(config_path)
    except HandshakeError as e:
        out.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from None

    _specs_dir = specs_dir or config.specs_dir
    try:
        spec_files = load_spec_files(_specs_dir)
    except HandshakeError as e:
        out.print(f"[red]Error loading specs: {e}[/red]")
        raise typer.Exit(1) from None

    if not spec_files:
        out.print("[yellow]No spec files found. Run 'handshake init' first.[/yellow]")
        raise typer.Exit(0)

    store = SnapshotStore(config.storage.path)
    replay_engine = ReplayEngine(store)
    adapters: dict[str, Any] = {}
    scenarios: list[Scenario] = []
    if not replay:
        try:
            adapters = load_adapters(config)
            scenarios = load_scenarios(config)
        except Exception as e:  # noqa: BLE001  # the user's adapters package can raise anything
            out.print(f"[red]Cannot run live: {e}[/red]")
            raise typer.Exit(1) from None
    else:
        try:
            scenarios = load_scenarios(config)
        except ConfigError:
            scenarios = []  # no scenario files: no expectations to check
    by_name = {sc.name: sc for sc in scenarios}
    checker = SpecChecker()

    records: list[dict[str, Any]] = []
    failed = 0

    mode_label = "[blue]replay[/blue]" if replay else "[yellow]live[/yellow]"
    if not report_only:
        out.print(f"\n[bold]agent-handshake[/bold] running tests ({mode_label} mode)\n")

    for spec_path, spec in spec_files:
        if replay:
            if not store.list_scenarios(spec.producer):
                out.print(
                    f"  [yellow]WARN: No snapshots for '{spec.producer}'. "
                    f"Run 'handshake record' first.[/yellow]"
                )
                continue
            cases = _replay_cases(spec, store, replay_engine, by_name)
        else:
            if spec.producer not in adapters:
                out.print(
                    f"  [yellow]WARN: No adapter for '{spec.producer}' in ADAPTERS; "
                    f"skipping {spec.name}.[/yellow]"
                )
                continue
            cases = _live_cases(spec, adapters[spec.producer], scenarios)

        if not report_only:
            out.print(f"  [bold]Spec: {spec.name}[/bold]")

        start = time.monotonic()
        for case in cases:
            scenario = case.scenario
            if case.output is None:
                out.print(f"    [red]FAIL[/red] {spec.name} / {scenario}: {case.error}")
                errors = [case.error or "no output"]
                passed_one = False
            else:
                result = checker.check(spec, case.output, case.input, case.expected)
                errors = result.failures()
                passed_one = result.passed
                if not report_only:
                    print_validation_result(
                        spec.name,
                        scenario,
                        result.structural,
                        result.policy,
                        expectation_errors=result.expectations,
                    )

            if not passed_one:
                failed += 1
                if format == OutputFormat.GITHUB:
                    for error in errors:
                        typer.echo(
                            format_github_annotation(
                                file=_annotation_path(spec_path),
                                line=1,
                                level="error",
                                message=f"{scenario}: {error}",
                                title=f"agent-handshake {spec.name}",
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
            start = time.monotonic()

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


def _replay_cases(
    spec: Spec, store: SnapshotStore, engine: ReplayEngine, by_name: dict[str, Scenario]
) -> Iterator[Case]:
    for scenario in store.list_scenarios(spec.producer):
        try:
            snapshot = engine.replay_snapshot(spec.producer, scenario)
        except SnapshotNotFoundError:
            yield Case(scenario, {}, error="snapshot not found")
            continue
        sc = by_name.get(scenario)
        expected = sc.expectations.get(spec.producer) if sc else None
        yield Case(scenario, snapshot.input_data, snapshot.output_data, expected=expected)


def _live_cases(spec: Spec, adapter: Any, scenarios: list[Scenario]) -> Iterator[Case]:
    """Call the producer for each scenario; nothing is saved."""
    for sc in scenarios:
        if not sc.applies_to(spec.producer):
            continue
        expected = sc.expectations.get(spec.producer)
        try:
            response = asyncio.run(adapter.call(sc.input))
        except Exception as e:  # noqa: BLE001  # a failing agent fails its case
            yield Case(sc.name, sc.input, error=f"agent call failed: {e}", expected=expected)
            continue
        yield Case(sc.name, sc.input, response.output, expected=expected)


def _annotation_path(path: Path) -> str:
    """Path for a GitHub annotation: relative to the repository root in Actions."""
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        try:
            return path.resolve().relative_to(Path(workspace).resolve()).as_posix()
        except ValueError:
            pass
    return str(path)
