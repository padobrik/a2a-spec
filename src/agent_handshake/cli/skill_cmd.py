"""a2aspec skill — export the bundled agent skill."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import typer
from rich.console import Console

console = Console(stderr=True)

SKILL_NAME = "a2a-spec"


def skill_text() -> str:
    """Return the SKILL.md bundled with this version of a2a-spec."""
    return (files("a2a_spec") / "skill" / "SKILL.md").read_text(encoding="utf-8")


def skill_command(
    dir: str | None = typer.Option(
        None,
        "--dir",
        "-d",
        help="Skills directory to install into, as <dir>/a2a-spec/SKILL.md. Default: print it.",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing SKILL.md."),
) -> None:
    """Export the agent skill that teaches coding agents the a2a-spec workflow.

    The skill matches the installed CLI version; re-export it after upgrading.
    """
    text = skill_text()
    if dir is None:
        typer.echo(text, nl=False)
        return

    target = Path(dir) / SKILL_NAME / "SKILL.md"
    if target.exists() and not force:
        console.print(f"[red]{target} already exists. Pass --force to overwrite.[/red]")
        raise typer.Exit(1)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    console.print(f"[green]Wrote {target}[/green]")
