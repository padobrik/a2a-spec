"""agent-handshake CLI entry point."""

from __future__ import annotations

import logging
import sys
import traceback

import typer
from rich.console import Console

from agent_handshake.cli.exit_codes import EXIT_INPUT
from agent_handshake.exceptions import HandshakeError

console = Console()

app = typer.Typer(
    name="handshake",
    help="agent-handshake checks that what your agent is told matches the tools it actually has.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


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
    """agent-handshake checks that what your agent is told matches the tools it actually has."""
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


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
        sys.exit(EXIT_INPUT)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001  # last resort: report any bug with its traceback
        console.print(f"\n[red]Unexpected error:[/red] {e}")
        console.print("[dim]This is a bug. Please report it with the traceback below.[/dim]\n")
        traceback.print_exc()
        sys.exit(EXIT_INPUT)
