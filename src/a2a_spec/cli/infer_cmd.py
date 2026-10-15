"""a2aspec infer — generate a consumer-driven spec."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from a2a_spec.config.loader import load_config
from a2a_spec.exceptions import A2ASpecError
from a2a_spec.infer.builder import infer_spec
from a2a_spec.infer.consumer import analyze_consumer, parse_source_ref
from a2a_spec.snapshot.store import SnapshotStore

console = Console(stderr=True)


def infer_command(
    producer: str = typer.Option(..., "--producer", "-p", help="Producer agent id."),
    consumer: str = typer.Option(..., "--consumer", "-C", help="Consumer agent id."),
    source: str = typer.Option(
        ...,
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
