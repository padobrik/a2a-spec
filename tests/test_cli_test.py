"""Tests for CLI test command."""

from __future__ import annotations

from typer.testing import CliRunner

from a2a_spec.cli.main import app

runner = CliRunner()


class TestCliTest:
    def test_test_help(self) -> None:
        result = runner.invoke(app, ["test", "--help"])
        assert result.exit_code == 0
        assert "replay" in result.output.lower() or "spec" in result.output.lower()

    def test_test_no_specs_dir(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "a2a-spec.yaml"
        config.write_text('project_name: test\nspecs_dir: "./nonexistent"')
        result = runner.invoke(app, ["test", "--config", str(config)])
        assert result.exit_code != 0

    def test_test_empty_specs(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        specs = tmp_path / "specs"
        specs.mkdir()
        config = tmp_path / "a2a-spec.yaml"
        config.write_text(f'project_name: test\nspecs_dir: "{specs}"')
        result = runner.invoke(app, ["test", "--config", str(config)])
        assert result.exit_code == 0

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
