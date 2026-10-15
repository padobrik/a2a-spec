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
        assert "0.2.0" in result.output


SPEC_YAML = """
spec:
  name: triage-to-resolution
  version: "1.0"
  producer: triage-agent
  consumer: resolution-agent
  structural:
    type: object
    required: [summary]
  semantic:
    - rule: summary_reflects_input
      method: embedding_similarity
      threshold: 0.8
      source_field: message
      target_field: summary
"""


class _FakeEncoder:
    def encode(self, texts: str | list[str]) -> list[list[float]]:
        vectors = {"charged twice": [1.0, 0.0], "duplicate charge": [0.9, 0.1]}
        return [vectors.get(t, [0.0, 1.0]) for t in texts]


class _MissingExtraEncoder:
    def encode(self, texts: str | list[str]) -> list[list[float]]:
        raise ImportError("sentence-transformers is required for semantic features.")


def _project(tmp_path, summary: str):
    import json

    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "triage.yaml").write_text(SPEC_YAML)
    snaps = tmp_path / "snapshots" / "triage-agent"
    snaps.mkdir(parents=True)
    (snaps / "billing_abc123.json").write_text(
        json.dumps(
            {
                "fingerprint": "abc123",
                "agent_id": "triage-agent",
                "scenario": "billing",
                "input": {"message": "charged twice"},
                "output": {"summary": summary},
            }
        )
    )
    config = tmp_path / "a2a-spec.yaml"
    config.write_text(
        f'project_name: test\nspecs_dir: "{specs}"\nstorage:\n  path: "{tmp_path / "snapshots"}"'
    )
    return config


def _use_encoder(monkeypatch, encoder: object) -> None:
    from a2a_spec.cli import test_cmd
    from a2a_spec.semantic.engine import SemanticEngine

    monkeypatch.setattr(test_cmd, "SemanticEngine", lambda **_: SemanticEngine(model=encoder))


class TestCliTestSemantic:
    def test_semantic_pass(self, tmp_path, monkeypatch) -> None:
        _use_encoder(monkeypatch, _FakeEncoder())
        config = _project(tmp_path, "duplicate charge")
        result = runner.invoke(app, ["test", "--config", str(config)])
        assert result.exit_code == 0, result.output
        assert "semantic PASS" in result.output

    def test_semantic_drift_fails(self, tmp_path, monkeypatch) -> None:
        _use_encoder(monkeypatch, _FakeEncoder())
        config = _project(tmp_path, "package lost in transit")
        result = runner.invoke(app, ["test", "--config", str(config)])
        assert result.exit_code == 1
        assert "FAIL triage-to-resolution / billing" in result.output
        assert "semantic FAIL" in result.output
        assert "summary_reflects_input: similarity 0.00 < threshold 0.80" in result.output

    def test_missing_extra_errors(self, tmp_path, monkeypatch) -> None:
        _use_encoder(monkeypatch, _MissingExtraEncoder())
        config = _project(tmp_path, "duplicate charge")
        result = runner.invoke(app, ["test", "--config", str(config)])
        assert result.exit_code == 1
        assert "sentence-transformers is required" in result.output
        assert "--no-semantic" in result.output

    def test_no_semantic_skips_visibly(self, tmp_path, monkeypatch) -> None:
        _use_encoder(monkeypatch, _MissingExtraEncoder())
        config = _project(tmp_path, "package lost in transit")
        result = runner.invoke(app, ["test", "--config", str(config), "--no-semantic"])
        assert result.exit_code == 0, result.output
        assert "semantic SKIPPED" in result.output

    def test_config_disabled_skips_visibly(self, tmp_path, monkeypatch) -> None:
        _use_encoder(monkeypatch, _MissingExtraEncoder())
        config = _project(tmp_path, "package lost in transit")
        config.write_text(config.read_text() + "\nsemantic:\n  enabled: false\n")
        result = runner.invoke(app, ["test", "--config", str(config)])
        assert result.exit_code == 0, result.output
        assert "semantic SKIPPED" in result.output
