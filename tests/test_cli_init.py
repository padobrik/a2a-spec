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


class TestInitTemplatesWork:
    """The generated project must behave correctly, not only exist."""

    def _init(self, tmp_path: Path, monkeypatch) -> Path:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "--name", "demo"])
        assert result.exit_code == 0, result.output
        return tmp_path

    def test_example_policy_catches_pii(self, tmp_path: Path, monkeypatch) -> None:
        from a2a_spec.policy.engine import PolicyEngine
        from a2a_spec.spec.loader import load_spec

        root = self._init(tmp_path, monkeypatch)
        spec = load_spec(root / "a2a_spec" / "specs" / "example-spec.yaml")
        engine = PolicyEngine()
        for leak in ("card 4111 1111 1111 1111 on file", "ssn 123-45-6789 on file"):
            [result] = engine.evaluate({"summary": leak}, {}, spec.policy)
            assert not result.passed, leak
        [clean] = engine.evaluate({"summary": "order #12345 charged twice"}, {}, spec.policy)
        assert clean.passed

    def test_example_semantic_rule_is_evaluable(self, tmp_path: Path, monkeypatch) -> None:
        from a2a_spec.semantic.engine import SemanticEngine
        from a2a_spec.spec.loader import load_spec

        class SameVector:
            def encode(self, texts: str | list[str]) -> list[list[float]]:
                return [[1.0, 0.0] for _ in texts]

        root = self._init(tmp_path, monkeypatch)
        spec = load_spec(root / "a2a_spec" / "specs" / "example-spec.yaml")
        results = SemanticEngine(model=SameVector()).evaluate(
            {"summary": "Customer was charged twice"},
            {"message": "I was charged twice for my order"},
            spec.semantic,
        )
        assert [r.passed for r in results] == [True], [r.detail for r in results]

    def test_empty_adapters_template_gives_guidance(self, tmp_path: Path, monkeypatch) -> None:
        self._init(tmp_path, monkeypatch)
        result = runner.invoke(app, ["record"])
        assert result.exit_code == 1
        assert "No adapters found" in result.output
