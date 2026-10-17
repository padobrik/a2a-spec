"""The handshake command: help and version."""

from __future__ import annotations

import sys

import pytest
from typer.testing import CliRunner

from agent_handshake import __version__
from agent_handshake.cli import main as cli_main
from agent_handshake.cli.exit_codes import EXIT_INPUT
from agent_handshake.cli.main import app
from agent_handshake.exceptions import ConfigError

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


def test_debug_flag() -> None:
    assert runner.invoke(app, ["--debug", "--help"]).exit_code == 0


@pytest.mark.parametrize(
    ("error", "code", "text"),
    [
        (KeyboardInterrupt(), 130, "Interrupted."),
        (RuntimeError("boom"), EXIT_INPUT, "Unexpected error: boom"),
    ],
)
def test_main_handles_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: BaseException,
    code: int,
    text: str,
) -> None:
    def broken() -> None:
        raise error

    monkeypatch.setattr(cli_main, "app", broken)
    with pytest.raises(SystemExit) as info:
        cli_main.main()
    assert info.value.code == code
    assert text in capsys.readouterr().out


def test_main_shows_the_traceback_with_debug(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> None:
        raise ConfigError("bad config")

    monkeypatch.setattr(cli_main, "app", broken)
    monkeypatch.setattr(sys, "argv", ["handshake", "--debug"])
    with pytest.raises(SystemExit) as info:
        cli_main.main()
    assert info.value.code == EXIT_INPUT
    captured = capsys.readouterr()
    assert "Error: bad config" in captured.out
    assert "Traceback" in captured.err
