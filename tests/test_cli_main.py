"""The handshake command: help and version."""

from __future__ import annotations

from typer.testing import CliRunner

from agent_handshake import __version__
from agent_handshake.cli.main import app

runner = CliRunner()


def test_help_describes_the_product() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "checks that what your agent is told matches the tools" in " ".join(
        result.output.split()
    )


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"agent-handshake {__version__}"
