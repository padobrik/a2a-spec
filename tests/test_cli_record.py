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
