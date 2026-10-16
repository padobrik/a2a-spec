"""Tests for CLI init command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from agent_handshake.cli.main import app

runner = CliRunner()


class TestCliInit:
    def test_init_creates_structure(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path), "--name", "test-project"])
        assert result.exit_code == 0
        assert (tmp_path / "handshake.yaml").exists()
        assert (tmp_path / "handshake" / "specs").is_dir()
        assert (tmp_path / "handshake" / "snapshots").is_dir()
        assert (tmp_path / "handshake" / "scenarios").is_dir()

    def test_init_creates_example_spec(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        assert (tmp_path / "handshake" / "specs" / "example-spec.yaml").exists()

    def test_init_creates_example_scenario(self, tmp_path: Path) -> None:
        runner.invoke(app, ["init", str(tmp_path)])
        assert (tmp_path / "handshake" / "scenarios" / "example-scenarios.yaml").exists()

    def test_init_does_not_overwrite_config(self, tmp_path: Path) -> None:
        config = tmp_path / "handshake.yaml"
        config.write_text("existing: true")
        runner.invoke(app, ["init", str(tmp_path)])
        assert "existing: true" in config.read_text()

    def test_init_keeps_yml_config(self, tmp_path: Path) -> None:
        (tmp_path / "handshake.yml").write_text("project_name: kept\n")
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert "Exists" in result.output
        assert "handshake.yml" in result.output
        assert not (tmp_path / "handshake.yaml").exists()

    def test_init_creates_gitignore(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".gitignore").read_text() == "__pycache__/\n"

    def test_init_appends_to_gitignore(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("# mine\nnode_modules/")
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert gitignore.read_text() == "# mine\nnode_modules/\n__pycache__/\n"
        assert "Updated .gitignore" in result.output

    def test_init_keeps_gitignore_that_has_the_lines(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("__pycache__\n")
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert gitignore.read_text() == "__pycache__\n"

    def test_init_default_project_name(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config_text = (tmp_path / "handshake.yaml").read_text()
        assert tmp_path.name in config_text

    def test_init_output_contains_success(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert "initialized" in result.output.lower() or "✓" in result.output


class TestInitTemplatesWork:
    """The generated project must behave correctly, not only exist."""

    def _init(self, tmp_path: Path, monkeypatch) -> Path:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "--name", "demo"])
        assert result.exit_code == 0, result.output
        return tmp_path

    def test_example_policy_catches_internal_ids(self, tmp_path: Path, monkeypatch) -> None:
        from agent_handshake.policy.engine import PolicyEngine
        from agent_handshake.spec.loader import load_spec

        root = self._init(tmp_path, monkeypatch)
        spec = load_spec(root / "handshake" / "specs" / "example-spec.yaml")
        engine = PolicyEngine()
        [leak] = engine.evaluate({"summary": "escalated as INT-004211"}, {}, spec.policy)
        assert not leak.passed
        [clean] = engine.evaluate({"summary": "order #12345 charged twice"}, {}, spec.policy)
        assert clean.passed

    def test_empty_adapters_template_gives_guidance(self, tmp_path: Path, monkeypatch) -> None:
        self._init(tmp_path, monkeypatch)
        result = runner.invoke(app, ["record"])
        assert result.exit_code == 2
        assert "No adapters found" in result.output
