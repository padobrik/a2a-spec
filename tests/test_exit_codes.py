"""Exit codes: 0 all good, 1 contract broken or serious drift, 2 configuration or input error."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_handshake.cli import main as cli_main
from agent_handshake.cli.exit_codes import EXIT_FAILED, EXIT_INPUT, EXIT_OK
from agent_handshake.cli.main import app
from agent_handshake.exceptions import ConfigError

runner = CliRunner()


def _spec(name: str, producer: str) -> str:
    return f"""spec:
  name: {name}
  version: "1.0"
  producer: {producer}
  consumer: resolution
  structural:
    type: object
    required: [category]
"""


def _snapshot(root: Path, agent: str, output: dict[str, object]) -> None:
    path = root / "handshake" / "snapshots" / agent / "billing_abc.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1,
        "agent_id": agent,
        "scenario": "billing",
        "input": {},
        "output": output,
    }
    path.write_text(json.dumps(data))


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "handshake.yaml").write_text("project_name: t\n")
    (tmp_path / "handshake" / "specs").mkdir(parents=True)
    return tmp_path


def _write_spec(root: Path, name: str, producer: str) -> None:
    (root / "handshake" / "specs" / f"{name}.yaml").write_text(_spec(name, producer))


def test_values() -> None:
    assert (EXIT_OK, EXIT_FAILED, EXIT_INPUT) == (0, 1, 2)


def test_all_pass(project: Path) -> None:
    _write_spec(project, "t2r", "triage")
    _snapshot(project, "triage", {"category": "billing"})
    assert runner.invoke(app, ["test"]).exit_code == EXIT_OK


def test_broken_contract(project: Path) -> None:
    _write_spec(project, "t2r", "triage")
    _snapshot(project, "triage", {"issue_type": "billing"})
    assert runner.invoke(app, ["test"]).exit_code == EXIT_FAILED


def test_spec_without_snapshots_is_an_input_error(project: Path) -> None:
    _write_spec(project, "t2r", "triage")
    result = runner.invoke(app, ["test"])
    assert result.exit_code == EXIT_INPUT
    out = " ".join(result.output.split())
    assert "ERROR No snapshots for 'triage', the producer of spec 't2r'" in out
    assert "1 input error(s); the run is not complete." in out


def test_input_error_wins_over_a_failure(project: Path) -> None:
    _write_spec(project, "t2r", "triage")
    _snapshot(project, "triage", {"issue_type": "billing"})
    _write_spec(project, "g2r", "ghost")
    result = runner.invoke(app, ["test"])
    assert result.exit_code == EXIT_INPUT
    assert "FAIL t2r / billing" in result.output


def test_handshake_errors_outside_commands_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> None:
        raise ConfigError("bad config")

    monkeypatch.setattr(cli_main, "app", broken)
    with pytest.raises(SystemExit) as info:
        cli_main.main()
    assert info.value.code == EXIT_INPUT
