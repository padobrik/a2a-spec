"""agent-handshake CLI entry point."""

from __future__ import annotations

import logging
import sys
import traceback

import typer
from rich.console import Console

from agent_handshake.cli.diff_cmd import diff_command
from agent_handshake.cli.infer_cmd import infer_command
from agent_handshake.cli.init_cmd import init_command
from agent_handshake.cli.pipeline_cmd import pipeline_app
from agent_handshake.cli.record_cmd import record_command
from agent_handshake.cli.skill_cmd import skill_command
from agent_handshake.cli.test_cmd import test_command
from agent_handshake.exceptions import HandshakeError

console = Console()

app = typer.Typer(
    name="handshake",
    help="agent-handshake — The open specification for agent-to-agent interactions.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

app.command("init")(init_command)
app.command("record")(record_command)
app.command("test")(test_command)
app.command("diff")(diff_command)
app.command("infer")(infer_command)
app.command("skill")(skill_command)
app.add_typer(pipeline_app, name="pipeline")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        from agent_handshake import __version__

        typer.echo(f"agent-handshake {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Show full tracebacks on error and enable debug logging.",
        is_eager=False,
    ),
) -> None:
    """agent-handshake — The open specification for agent-to-agent interactions."""
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
    else:
        logging.basicConfig(level=logging.WARNING)


def main() -> None:
    """CLI entry point with top-level error handling.

    Catches HandshakeError for user-friendly messages, KeyboardInterrupt
    for clean exits, and unexpected exceptions for bug reporting.
    """
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        sys.exit(130)
    except HandshakeError as e:
        console.print(f"\n[red]Error:[/red] {e}")
        if "--debug" in sys.argv or "-d" in sys.argv:
            console.print("\n[dim]Traceback:[/dim]")
            traceback.print_exc()
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001  # last resort: report any bug with its traceback
        console.print(f"\n[red]Unexpected error:[/red] {e}")
        console.print("[dim]This is a bug. Please report it with the traceback below.[/dim]\n")
        traceback.print_exc()
        sys.exit(2)
