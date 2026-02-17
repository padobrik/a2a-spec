"""Tests for CLI init command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from a2a_spec.cli.main import app

runner = CliRunner()


class TestCliInit:
    def test_init_creates_structure(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path), "--name", "test-project"])
        assert result.exit_code == 0
        assert (tmp_path / "a2a-spec.yaml").exists()
        assert (tmp_path / "a2a_spec" / "specs").is_dir()
        assert (tmp_path / "a2a_spec" / "snapshots").is_dir()
        assert (tmp_path / "a2a_spec" / "scenarios").is_dir()

    def test_init_creates_example_spec(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        assert (tmp_path / "a2a_spec" / "specs" / "example-spec.yaml").exists()

    def test_init_creates_example_scenario(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        assert (tmp_path / "a2a_spec" / "scenarios" / "example-scenarios.yaml").exists()

    def test_init_does_not_overwrite_config(self, tmp_path: Path) -> None:
        config = tmp_path / "a2a-spec.yaml"
        config.write_text("existing: true")
        runner.invoke(app, ["init", str(tmp_path)])
        assert "existing: true" in config.read_text()

    def test_init_default_project_name(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config_text = (tmp_path / "a2a-spec.yaml").read_text()
        assert tmp_path.name in config_text

    def test_init_output_contains_success(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert "initialized" in result.output.lower() or "✓" in result.output
