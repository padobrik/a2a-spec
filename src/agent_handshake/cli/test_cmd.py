"""handshake test — run spec validation."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from agent_handshake.api import check, load_snapshots
from agent_handshake.cli.exit_codes import EXIT_FAILED, EXIT_INPUT
from agent_handshake.config.loader import load_config
from agent_handshake.exceptions import ConfigError, HandshakeError, SnapshotFormatError
from agent_handshake.project import Scenario, load_adapters, load_scenarios
from agent_handshake.reporting.console import print_summary, print_validation_result
from agent_handshake.reporting.github import format_github_annotation
from agent_handshake.reporting.json_report import generate_json_report
from agent_handshake.reporting.junit import generate_junit_xml
from agent_handshake.reporting.markdown import generate_report
from agent_handshake.snapshot.fingerprint import Fingerprint
from agent_handshake.snapshot.store import Snapshot
from agent_handshake.spec.checker import SpecCheck
from agent_handshake.spec.loader import load_spec_files
from agent_handshake.spec.schema import Spec

console = Console()


@dataclass(frozen=True)
class Case:
    """One checked producer output, or the reason there is none."""

    scenario: str
    check: SpecCheck | None = None
    error: str | None = None


class OutputFormat(StrEnum):
    """Report formats for handshake test."""

    CONSOLE = "console"
    MARKDOWN = "markdown"
    JUNIT = "junit"
    GITHUB = "github"
    JSON = "json"


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
            help="console; markdown, junit or json (report only, on stdout); "
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
    report_only = format in (OutputFormat.MARKDOWN, OutputFormat.JUNIT, OutputFormat.JSON)
    out = Console(stderr=True) if report_only else console

    try:
        config = load_config(config_path)
    except HandshakeError as e:
        out.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(EXIT_INPUT) from None

    _specs_dir = specs_dir or config.specs_dir
    try:
        spec_files = load_spec_files(_specs_dir)
    except HandshakeError as e:
        out.print(f"[red]Error loading specs: {e}[/red]")
        raise typer.Exit(EXIT_INPUT) from None

    if not spec_files:
        out.print(
            f"[red]No spec files in {_specs_dir}. Write one, or run 'handshake infer' "
            "or 'handshake init'.[/red]"
        )
        raise typer.Exit(EXIT_INPUT)

    adapters: dict[str, Any] = {}
    scenarios: list[Scenario] = []
    snapshots: list[Snapshot] = []
    if not replay:
        try:
            adapters = load_adapters(config)
            scenarios = load_scenarios(config)
        except Exception as e:  # noqa: BLE001  # the user's adapters package can raise anything
            out.print(f"[red]Cannot run live: {e}[/red]")
            raise typer.Exit(EXIT_INPUT) from None
    else:
        try:
            scenarios = load_scenarios(config)
        except ConfigError:
            scenarios = []  # no scenario files: no expectations to check
        try:
            if Path(config.storage.path).exists():
                snapshots = load_snapshots(config.storage.path)
        except SnapshotFormatError as e:
            # A snapshot file that is not valid stops the run: it is an input error.
            out.print(f"[red]{e}[/red]")
            raise typer.Exit(EXIT_INPUT) from None

    records: list[dict[str, Any]] = []
    failed = 0
    # Problems with the input, such as a spec whose producer has no snapshots.
    # They make the run incomplete, so they are errors, not skips.
    input_errors: list[str] = []

    mode_label = "[blue]replay[/blue]" if replay else "[yellow]live[/yellow]"
    if not report_only:
        out.print(f"\n[bold]agent-handshake[/bold] running tests ({mode_label} mode)\n")

    for spec_path, spec in spec_files:
        expected = {sc.name: sc.expectations.get(spec.producer) or {} for sc in scenarios}
        if replay:
            result = check(spec, snapshots, expected)
            if result.errors:
                for error in result.errors:
                    out.print(f"  [red]ERROR[/red] {error}")
                input_errors += result.errors
                continue
            cases: Iterable[Case] = [Case(c.snapshot.scenario, check=c.check) for c in result.cases]
        else:
            if spec.producer not in adapters:
                error = (
                    f"No adapter for '{spec.producer}', the producer of spec '{spec.name}'. "
                    "Add it to ADAPTERS."
                )
                out.print(f"  [red]ERROR[/red] {error}")
                input_errors.append(error)
                continue
            cases = _live_cases(spec, adapters[spec.producer], scenarios, expected)

        if not report_only:
            out.print(f"  [bold]Spec: {spec.name}[/bold]")

        start = time.monotonic()
        for case in cases:
            scenario = case.scenario
            if case.check is None:
                out.print(f"    [red]FAIL[/red] {spec.name} / {scenario}: {case.error}")
                errors = [case.error or "no output"]
                passed_one = False
            else:
                errors = case.check.failures()
                passed_one = case.check.passed
                if not report_only:
                    print_validation_result(
                        spec.name,
                        scenario,
                        case.check.structural,
                        case.check.policy,
                        expectation_errors=case.check.expectations,
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
    elif format == OutputFormat.JSON:
        typer.echo(generate_json_report(records, project_name=config.project_name))
    else:
        print_summary(len(records), len(records) - failed, failed)

    if input_errors:
        out.print(f"[red]{len(input_errors)} input error(s); the run is not complete.[/red]")
        raise typer.Exit(EXIT_INPUT)
    if failed > 0:
        raise typer.Exit(EXIT_FAILED)


def _live_cases(
    spec: Spec, adapter: Any, scenarios: list[Scenario], expected: dict[str, dict[str, Any]]
) -> Iterator[Case]:
    """Call the producer for each scenario and check the output; nothing is saved."""
    for sc in scenarios:
        if not sc.applies_to(spec.producer):
            continue
        try:
            response = asyncio.run(adapter.call(sc.input))
        except Exception as e:  # noqa: BLE001  # a failing agent fails its case
            yield Case(sc.name, error=f"agent call failed: {e}")
            continue
        snapshot = Snapshot(
            fingerprint=Fingerprint.create(spec.producer, sc.input),
            scenario=sc.name,
            input_data=sc.input,
            output_data=response.output,
        )
        [case] = check(spec, [snapshot], expected).cases
        yield Case(sc.name, check=case.check)


def _annotation_path(path: Path) -> str:
    """Path for a GitHub annotation: relative to the repository root in Actions."""
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        try:
            return path.resolve().relative_to(Path(workspace).resolve()).as_posix()
        except ValueError:
            pass
    return str(path)
