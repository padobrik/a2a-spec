"""Exit codes: 0 all good, 1 contract broken or serious drift, 2 configuration or input error."""

from __future__ import annotations

import pytest

from agent_handshake.cli import main as cli_main
from agent_handshake.cli.exit_codes import EXIT_FAILED, EXIT_INPUT, EXIT_OK
from agent_handshake.exceptions import ConfigError


def test_values() -> None:
    assert (EXIT_OK, EXIT_FAILED, EXIT_INPUT) == (0, 1, 2)


def test_handshake_errors_outside_commands_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> None:
        raise ConfigError("bad config")

    monkeypatch.setattr(cli_main, "app", broken)
    with pytest.raises(SystemExit) as info:
        cli_main.main()
    assert info.value.code == EXIT_INPUT
