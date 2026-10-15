"""a2aspec infer — generate a consumer-driven spec."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from a2a_spec.config.loader import load_config
from a2a_spec.exceptions import A2ASpecError
from a2a_spec.infer.builder import infer_spec
from a2a_spec.infer.check import check_inferred_spec
from a2a_spec.infer.consumer import analyze_consumer, parse_source_ref
from a2a_spec.snapshot.store import SnapshotStore
from a2a_spec.spec.loader import load_spec_files

console = Console(stderr=True)


def infer_command(
    producer: str | None = typer.Option(None, "--producer", "-p", help="Producer agent id."),
    consumer: str | None = typer.Option(None, "--consumer", "-C", help="Consumer agent id."),
    source: str | None = typer.Option(
        None,
        "--source",
        help="Consumer function that reads the producer's output, as path/to/file.py:function.",
    ),
    name: str | None = typer.Option(None, "--name", "-n", help="Spec name."),
    out: str | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Output file, or '-' for stdout. Default: <specs_dir>/<name>.yaml.",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing spec file."),
    check: bool = typer.Option(
        False,
        "--check",
        help="Check every inferred spec against its consumer's current code; "
        "fail if the code reads fields the spec does not cover.",
    ),
    config_path: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file.",
    ),
) -> None:
    """Infer the contract a consumer needs from a producer.

    Reads the consumer's code to find which fields it uses and the
    producer's recorded snapshots to type them. Fields the consumer never
    reads are left out, so the producer can change them freely.
    """
    if check:
        _check(config_path)
        return
    if not (producer and consumer and source):
        console.print("[red]--producer, --consumer and --source are required.[/red]")
        raise typer.Exit(2)

    try:
        config = load_config(config_path)
        path, function = parse_source_ref(source)
        reads = analyze_consumer(path, function)
        snapshots = SnapshotStore(config.storage.path).load_all(producer)
    except (A2ASpecError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None

    if not snapshots:
        console.print(f"[red]No snapshots for '{producer}'. Run 'a2aspec record' first.[/red]")
        raise typer.Exit(1)
    if not reads.reads:
        console.print(f"[red]{source} reads no fields from its input.[/red]")
        for warning in reads.warnings:
            console.print(f"  [yellow]{warning}[/yellow]")
        raise typer.Exit(1)

    inferred = infer_spec(producer, consumer, reads, snapshots, name=name)
    text = inferred.to_yaml()

    for warning in inferred.warnings:
        console.print(f"[yellow]WARN: {warning}[/yellow]")

    if out == "-":
        typer.echo(text, nl=False)
        return

    target = Path(out) if out else Path(config.specs_dir) / f"{inferred.data['name']}.yaml"
    if target.exists() and not force:
        console.print(f"[red]{target} already exists. Pass --force to overwrite.[/red]")
        raise typer.Exit(1)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

    fields = inferred.data["structural"]["properties"]
    console.print(f"[green]Wrote {target}[/green] ({len(fields)} field(s) from {source})")


def _check(config_path: str | None) -> None:
    try:
        config = load_config(config_path)
        spec_files = load_spec_files(config.specs_dir)
    except A2ASpecError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None

    inferred = [(path, spec) for path, spec in spec_files if spec.inferred_from]
    if not inferred:
        console.print(
            "[yellow]No inferred specs to check. Specs made by 'a2aspec infer' "
            "record their consumer in 'inferred_from'.[/yellow]"
        )
        return

    stale = 0
    for path, spec in inferred:
        try:
            result = check_inferred_spec(spec)
        except A2ASpecError as e:
            console.print(f"[red]FAIL[/red] {spec.name}: {e}")
            stale += 1
            continue
        label = "[green]OK[/green]  " if result.passed else "[red]FAIL[/red]"
        console.print(f"{label} {spec.name} ({spec.inferred_from})")
        for failure in result.failures:
            console.print(f"    [red]{failure}[/red]")
        for warning in result.warnings:
            console.print(f"    [yellow]WARN: {warning}[/yellow]")
        if not result.passed:
            stale += 1
            console.print(
                f"    Regenerate: a2aspec infer --producer {spec.producer} "
                f"--consumer {spec.consumer} --source {spec.inferred_from} "
                f"--out {path} --force"
            )
    if stale:
        raise typer.Exit(1)
