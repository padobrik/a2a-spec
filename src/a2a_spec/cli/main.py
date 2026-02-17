"""a2a-spec CLI entry point."""

import typer

from a2a_spec.cli.diff_cmd import diff_command
from a2a_spec.cli.init_cmd import init_command
from a2a_spec.cli.pipeline_cmd import pipeline_app
from a2a_spec.cli.record_cmd import record_command
from a2a_spec.cli.test_cmd import test_command

app = typer.Typer(
    name="a2aspec",
    help="a2a-spec — The open specification for agent-to-agent interactions.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

app.command("init")(init_command)
app.command("record")(record_command)
app.command("test")(test_command)
app.command("diff")(diff_command)
app.add_typer(pipeline_app, name="pipeline")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        from a2a_spec import __version__

        typer.echo(f"a2a-spec {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """a2a-spec — The open specification for agent-to-agent interactions."""
