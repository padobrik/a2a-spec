"""Tests for CLI diff command."""

from __future__ import annotations

from typer.testing import CliRunner

from a2a_spec.cli.main import app

runner = CliRunner()


class TestCliDiff:
    def test_diff_help(self) -> None:
        result = runner.invoke(app, ["diff", "--help"])
        assert result.exit_code == 0
        assert "threshold" in result.output.lower() or "diff" in result.output.lower()

    def test_diff_no_snapshots(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "a2a-spec.yaml"
        config.write_text(f'project_name: test\nstorage:\n  path: "{tmp_path / "empty_snaps"}"')
        result = runner.invoke(app, ["diff", "--config", str(config)])
        assert result.exit_code == 0

    def test_diff_invalid_config(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "bad.yaml"
        config.write_text("- not a mapping")
        result = runner.invoke(app, ["diff", "--config", str(config)])
        assert result.exit_code != 0

    def test_diff_custom_threshold(self) -> None:
        result = runner.invoke(app, ["diff", "--help"])
        assert "threshold" in result.output.lower()
