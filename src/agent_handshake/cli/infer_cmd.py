"""handshake infer — generate a consumer-driven spec."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from agent_handshake.cli.exit_codes import EXIT_FAILED, EXIT_INPUT
from agent_handshake.config.loader import load_config
from agent_handshake.exceptions import HandshakeError
from agent_handshake.infer.builder import infer_spec
from agent_handshake.infer.check import check_inferred_spec
from agent_handshake.infer.consumer import analyze_consumer, parse_source_ref
from agent_handshake.snapshot.store import SnapshotStore
from agent_handshake.spec.loader import load_spec_files

console = Console(stderr=True)


def infer_command(
    producer: str | None = typer.Option(None, "--producer", "-p", help="Producer agent id."),
    consumer: str | None = typer.Option(None, "--consumer", "-C", help="Consumer agent id."),
    source: str | None = typer.Option(
        None,
        "--source",
        help="Consumer function that reads the producer's output, as path/to/file.py:function. "
        ".ts, .mts, .cts, .tsx, .js, .jsx, .mjs and .cjs files need the 'typescript' extra.",
    ),
    name: str | None = typer.Option(None, "--name", "-n", help="Spec name."),
    out: str | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Output file, or '-' for stdout. Default: <specs_dir>/<name>.yaml.",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing spec file."),
    allow_missing: Annotated[
        list[str] | None,
        typer.Option(
            "--allow-missing",
            help="A field the consumer reads that the producer leaves out on purpose, as a "
            "dotted path. Without it such a field is an error. Repeat for more fields.",
        ),
    ] = None,
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
        raise typer.Exit(EXIT_INPUT)

    try:
        config = load_config(config_path)
        path, function = parse_source_ref(source)
        reads = analyze_consumer(path, function)
        snapshots = SnapshotStore(config.storage.path).load_all(producer)
    except (HandshakeError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(EXIT_INPUT) from None

    if not snapshots:
        console.print(f"[red]No snapshots for '{producer}'. Run 'handshake record' first.[/red]")
        raise typer.Exit(EXIT_INPUT)
    if not reads.reads:
        console.print(f"[red]{source} reads no fields from its input.[/red]")
        for warning in reads.warnings:
            console.print(f"  [yellow]{warning}[/yellow]")
        raise typer.Exit(EXIT_INPUT)

    inferred = infer_spec(
        producer, consumer, reads, snapshots, name=name, allow_missing=allow_missing or []
    )
    text = inferred.to_yaml()

    for warning in inferred.warnings:
        console.print(f"[yellow]WARN: {warning}[/yellow]")
    if inferred.missing:
        for problem in inferred.missing:
            console.print(f"[red]FAIL: {problem}[/red]")
        console.print(
            "[red]No spec written.[/red] Fix the producer and run 'handshake record' again, "
            "or pass --allow-missing FIELD if the producer leaves the field out on purpose."
        )
        raise typer.Exit(EXIT_FAILED)

    if out == "-":
        typer.echo(text, nl=False)
        return

    target = Path(out) if out else Path(config.specs_dir) / f"{inferred.data['name']}.yaml"
    if target.exists() and not force:
        console.print(f"[red]{target} already exists. Pass --force to overwrite.[/red]")
        raise typer.Exit(EXIT_INPUT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

    fields = inferred.data["structural"]["properties"]
    console.print(f"[green]Wrote {target}[/green] ({len(fields)} field(s) from {source})")


def _check(config_path: str | None) -> None:
    try:
        config = load_config(config_path)
        spec_files = load_spec_files(config.specs_dir)
    except HandshakeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(EXIT_INPUT) from None

    inferred = [(path, spec) for path, spec in spec_files if spec.inferred_from]
    if not inferred:
        console.print(
            "[yellow]No inferred specs found, nothing to check. Specs made by "
            "'handshake infer' record their consumer in 'inferred_from'.[/yellow]"
        )
        return

    stale = 0
    broken = 0
    for path, spec in inferred:
        try:
            result = check_inferred_spec(spec)
        except HandshakeError as e:
            console.print(f"[red]ERROR[/red] {spec.name}: {e}")
            broken += 1
            continue
        label = "[green]OK[/green]  " if result.passed else "[red]FAIL[/red]"
        console.print(f"{label} {spec.name} ({spec.inferred_from})")
        for failure in result.failures:
            console.print(f"    [red]{failure}[/red]")
        for warning in result.warnings:
            console.print(f"    [yellow]WARN: {warning}[/yellow]")
        if not result.passed:
            stale += 1
            allowed = "".join(f" --allow-missing {shlex.quote(n)}" for n in spec.allow_missing)
            console.print(
                f"    Regenerate: handshake infer --producer {spec.producer} "
                f"--consumer {spec.consumer} --source {spec.inferred_from} "
                f"--out {path} --force{allowed}"
            )
    if broken:
        raise typer.Exit(EXIT_INPUT)
    if stale:
        raise typer.Exit(EXIT_FAILED)
