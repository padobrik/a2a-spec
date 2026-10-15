"""Tests for CLI record command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from a2a_spec.cli.main import app

runner = CliRunner()


class TestCliRecord:
    def test_record_no_scenarios_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "a2a-spec.yaml"
        config.write_text('project_name: test\nscenarios_dir: "./nonexistent"')
        result = runner.invoke(app, ["record", "--config", str(config)])
        assert result.exit_code != 0

    def test_record_no_adapters(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        scenarios = tmp_path / "scenarios"
        scenarios.mkdir()
        (scenarios / "test.yaml").write_text("test_suite:\n  name: test\nscenarios: []")
        config = tmp_path / "a2a-spec.yaml"
        config.write_text(
            f'project_name: test\nscenarios_dir: "{scenarios}"\n'
            f'storage:\n  path: "{tmp_path / "snaps"}"'
        )
        result = runner.invoke(app, ["record", "--config", str(config)])
        assert result.exit_code != 0

    def test_record_invalid_config(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "bad.yaml"
        config.write_text("- not a mapping")
        result = runner.invoke(app, ["record", "--config", str(config)])
        assert result.exit_code != 0

    def test_record_help(self) -> None:
        result = runner.invoke(app, ["record", "--help"])
        assert result.exit_code == 0
        assert "record" in result.output.lower()


SCENARIOS = """
test_suite:
  name: support
scenarios:
  - name: billing
    input:
      message: "charged twice"
"""


def _project(tmp_path: Path, adapters_init: str) -> Path:
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "triage.py").write_text(
        "async def triage(data):\n    return {'category': 'billing', 'echo': data['message']}\n"
    )
    adapters = tmp_path / "a2a_spec" / "adapters"
    adapters.mkdir(parents=True)
    (adapters / "triage_adapter.py").write_text(
        "from a2a_spec import FunctionAdapter\n"
        "from agents.triage import triage\n"
        "adapter = FunctionAdapter(fn=triage, agent_id='triage-agent', version='1.0')\n"
    )
    (adapters / "__init__.py").write_text(adapters_init)
    scenarios = tmp_path / "a2a_spec" / "scenarios"
    scenarios.mkdir()
    (scenarios / "support.yaml").write_text(SCENARIOS)
    config = tmp_path / "a2a-spec.yaml"
    config.write_text("project_name: test\n")
    return config


def _flat(text: str) -> str:
    return " ".join(text.split())


class TestCliRecordAdapters:
    def test_records_with_project_adapters(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _project(
            tmp_path,
            "from .triage_adapter import adapter\nADAPTERS = {'triage-agent': adapter}\n",
        )
        result = runner.invoke(app, ["record", "--config", str(config)])
        assert result.exit_code == 0, result.output
        assert "triage-agent / billing recorded" in _flat(result.output)
        assert "[record] Recording snapshots" in result.output
        assert "[done] 1 snapshots saved" in _flat(result.output)

        from a2a_spec.snapshot.store import SnapshotStore

        snap = SnapshotStore(tmp_path / "a2a_spec" / "snapshots").load("triage-agent", "billing")
        assert snap.output_data == {"category": "billing", "echo": "charged twice"}

    def test_adapter_import_error_is_reported(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _project(tmp_path, "import not_a_real_module_xyz\nADAPTERS = {}\n")
        result = runner.invoke(app, ["record", "--config", str(config)])
        assert result.exit_code == 1
        assert "Failed to load adapters" in _flat(result.output)
        assert "not_a_real_module_xyz" in _flat(result.output)

    def test_missing_adapters_mapping(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _project(tmp_path, "x = 1\n")
        result = runner.invoke(app, ["record", "--config", str(config)])
        assert result.exit_code == 1
        assert "must define ADAPTERS" in _flat(result.output)

    def test_missing_adapters_package(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _project(tmp_path, "ADAPTERS = {}\n")
        config.write_text("project_name: test\nadapters_dir: ./elsewhere\n")
        result = runner.invoke(app, ["record", "--config", str(config)])
        assert result.exit_code == 1
        assert "No adapters package at" in _flat(result.output)
