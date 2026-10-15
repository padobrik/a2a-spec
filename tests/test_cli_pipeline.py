"""Tests for the pipeline test command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from a2a_spec.cli.main import app

runner = CliRunner()

SPEC = """
spec:
  name: triage-to-resolution
  version: "1.0"
  producer: triage-agent
  consumer: resolution-agent
  structural:
    type: object
    required: [category]
"""

PIPELINE = """
pipeline:
  name: support
  agents:
    triage-agent: {}
    resolution-agent: {}
  edges:
    - from: triage-agent
      to: resolution-agent
  test_cases:
    - name: billing
      input: {message: "charged twice"}
"""


def _adapters(triage_output: str, with_triage: bool = True) -> str:
    entries = (
        '"resolution-agent": FunctionAdapter(fn=res, agent_id="resolution-agent", version="1")'
    )
    if with_triage:
        entries = (
            '"triage-agent": FunctionAdapter(fn=triage, agent_id="triage-agent", version="1"), '
            + entries
        )
    return (
        "from a2a_spec import FunctionAdapter\n"
        f"async def triage(data):\n    return {triage_output}\n"
        "async def res(ticket):\n    return {'reply': 'ok'}\n"
        f"ADAPTERS = {{{entries}}}\n"
    )


def _project(tmp_path: Path, adapters: str) -> None:
    root = tmp_path / "a2a_spec"
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "t2r.yaml").write_text(SPEC)
    (root / "adapters").mkdir()
    (root / "adapters" / "__init__.py").write_text(adapters)
    (tmp_path / "pipeline.yaml").write_text(PIPELINE)
    (tmp_path / "a2a-spec.yaml").write_text("project_name: demo\n")


def _flat(text: str) -> str:
    return " ".join(text.split())


class TestPipelineCli:
    def test_live_calls_agents(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _project(tmp_path, _adapters("{'category': 'billing'}"))
        result = runner.invoke(app, ["pipeline", "test", "pipeline.yaml", "--mode", "live"])
        assert result.exit_code == 0, result.output
        out = _flat(result.output)
        assert "[test] Pipeline: support (live mode)" in out
        assert "PASS triage-agent" in out
        assert "NO SPEC resolution-agent" in out

    def test_live_spec_violation_fails(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _project(tmp_path, _adapters("{'issue_type': 'billing'}"))
        result = runner.invoke(app, ["pipeline", "test", "pipeline.yaml", "--mode", "live"])
        assert result.exit_code == 1
        out = _flat(result.output)
        assert "FAIL Pipeline: support / billing" in out
        assert "'category' is a required property" in out

    def test_missing_adapter_fails_the_case(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _project(tmp_path, _adapters("{}", with_triage=False))
        result = runner.invoke(app, ["pipeline", "test", "pipeline.yaml", "--mode", "live"])
        assert result.exit_code == 1
        assert "No adapter registered for 'triage-agent'" in _flat(result.output)
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_replay_uses_snapshots(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _project(tmp_path, "ADAPTERS = {}\n")
        for agent, output in (("triage-agent", {"category": "billing"}), ("resolution-agent", {})):
            d = tmp_path / "a2a_spec" / "snapshots" / agent
            d.mkdir(parents=True)
            (d / "billing_abc.json").write_text(
                json.dumps(
                    {
                        "fingerprint": "abc",
                        "agent_id": agent,
                        "scenario": "billing",
                        "input": {},
                        "output": output,
                    }
                )
            )
        result = runner.invoke(app, ["pipeline", "test", "pipeline.yaml"])
        assert result.exit_code == 0, result.output
        assert "(replay mode)" in result.output

    def test_unknown_mode_rejected(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _project(tmp_path, "ADAPTERS = {}\n")
        result = runner.invoke(app, ["pipeline", "test", "pipeline.yaml", "--mode", "fast"])
        assert result.exit_code == 2
