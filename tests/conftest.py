"""Shared test fixtures."""

from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def _cli_never_crashes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CLI call ends in an exit code and a message, never in a traceback."""
    invoke = CliRunner.invoke

    def checked(self: CliRunner, *args: Any, **kwargs: Any) -> Any:
        result = invoke(self, *args, **kwargs)
        crashed = result.exception is not None and not isinstance(result.exception, SystemExit)
        assert not crashed, f"CLI raised {result.exception!r}:\n{result.output}"
        assert "Traceback" not in result.output, result.output
        return result

    monkeypatch.setattr(CliRunner, "invoke", checked)
