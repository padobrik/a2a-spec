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
        assert "0.5.0" in result.output


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


STRUCT_SPEC = """
spec:
  name: triage-to-resolution
  version: "1.0"
  producer: triage-agent
  consumer: resolution-agent
  structural:
    type: object
    required: [category]
"""


def _struct_project(tmp_path, outputs: dict[str, dict]):
    import json

    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "triage.yaml").write_text(STRUCT_SPEC)
    snaps = tmp_path / "snapshots" / "triage-agent"
    snaps.mkdir(parents=True)
    for scenario, output in outputs.items():
        (snaps / f"{scenario}_abc123.json").write_text(
            json.dumps(
                {
                    "fingerprint": "abc123",
                    "agent_id": "triage-agent",
                    "scenario": scenario,
                    "input": {"message": "hi"},
                    "output": output,
                }
            )
        )
    config = tmp_path / "a2a-spec.yaml"
    config.write_text(
        f'project_name: demo\nspecs_dir: "{specs}"\nstorage:\n  path: "{tmp_path / "snapshots"}"\n'
    )
    return config


OUTPUTS = {"billing": {"category": "billing"}, "renamed": {"issue_type": "billing"}}


class TestCliTestFormats:
    def test_junit_is_clean_xml(self, tmp_path) -> None:
        import xml.etree.ElementTree as ET

        config = _struct_project(tmp_path, OUTPUTS)
        result = runner.invoke(app, ["test", "--config", str(config), "--format", "junit"])
        assert result.exit_code == 1
        suite = ET.fromstring(result.stdout.split("?>", 1)[1])
        assert suite.get("name") == "demo"
        assert suite.get("tests") == "2" and suite.get("failures") == "1"
        [failure] = suite.iter("failure")
        assert "'category' is a required property" in failure.get("message", "")
        names = {tc.get("name"): tc.get("classname") for tc in suite.iter("testcase")}
        assert names == {"billing": "triage-to-resolution", "renamed": "triage-to-resolution"}

    def test_markdown_report(self, tmp_path) -> None:
        config = _struct_project(tmp_path, OUTPUTS)
        result = runner.invoke(app, ["test", "--config", str(config), "--format", "markdown"])
        assert result.exit_code == 1
        assert result.stdout.startswith("# a2a-spec Report: demo")
        assert "**1/2 passed** | 1 failed" in result.stdout
        assert "### triage-to-resolution / renamed" in result.stdout
        assert "Spec:" not in result.stdout

    def test_github_annotations(self, tmp_path) -> None:
        config = _struct_project(tmp_path, OUTPUTS)
        result = runner.invoke(app, ["test", "--config", str(config), "--format", "github"])
        assert result.exit_code == 1
        lines = [line for line in result.stdout.splitlines() if line.startswith("::error")]
        assert len(lines) == 1
        spec_path = tmp_path / "specs" / "triage.yaml"
        assert lines[0].startswith(
            f"::error file={spec_path},line=1,title=a2a-spec triage-to-resolution::"
        )
        assert "renamed: structural: [<root>] 'category' is a required property" in lines[0]

    def test_passing_run_has_no_annotations(self, tmp_path) -> None:
        config = _struct_project(tmp_path, {"billing": {"category": "billing"}})
        result = runner.invoke(app, ["test", "--config", str(config), "--format", "github"])
        assert result.exit_code == 0
        assert "::error" not in result.stdout

    def test_unknown_format_rejected(self, tmp_path) -> None:
        config = _struct_project(tmp_path, OUTPUTS)
        result = runner.invoke(app, ["test", "--config", str(config), "--format", "html"])
        assert result.exit_code == 2


LIVE_ADAPTERS = """
from a2a_spec import FunctionAdapter

async def triage(data):
    if "boom" in data["message"]:
        raise RuntimeError("model down")
    key = "issue_type" if "rename" in data["message"] else "category"
    return {key: "billing"}

ADAPTERS = {"triage-agent": FunctionAdapter(fn=triage, agent_id="triage-agent", version="1")}
"""


def _live_project(tmp_path, messages: dict[str, str], adapters: str = LIVE_ADAPTERS):
    specs = tmp_path / "a2a_spec" / "specs"
    specs.mkdir(parents=True)
    (specs / "triage.yaml").write_text(STRUCT_SPEC)
    pkg = tmp_path / "a2a_spec" / "adapters"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(adapters)
    scenarios = tmp_path / "a2a_spec" / "scenarios"
    scenarios.mkdir()
    body = "".join(
        f"  - name: {name}\n    input:\n      message: {msg}\n" for name, msg in messages.items()
    )
    (scenarios / "s.yaml").write_text("scenarios:\n" + body)
    (tmp_path / "a2a-spec.yaml").write_text("project_name: demo\n")


class TestCliTestLive:
    def test_live_checks_producer_output_without_snapshots(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _live_project(tmp_path, {"ok": "charged twice", "renamed": "please rename"})
        result = runner.invoke(app, ["test", "--live"])
        assert result.exit_code == 1, result.output
        assert "PASS triage-to-resolution / ok" in result.output
        assert "FAIL triage-to-resolution / renamed" in result.output
        assert "'category' is a required property" in result.output
        assert not (tmp_path / "a2a_spec" / "snapshots").exists()

    def test_live_all_pass(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _live_project(tmp_path, {"ok": "charged twice"})
        result = runner.invoke(app, ["test", "--live"])
        assert result.exit_code == 0, result.output
        assert "1 passed" in result.output

    def test_agent_error_fails(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _live_project(tmp_path, {"broken": "boom"})
        result = runner.invoke(app, ["test", "--live"])
        assert result.exit_code == 1
        assert "agent call failed: " in result.output and "model down" in result.output

    def test_producer_without_adapter_is_skipped(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _live_project(tmp_path, {"ok": "charged twice"}, adapters="ADAPTERS = {}\n")
        result = runner.invoke(app, ["test", "--live"])
        assert result.exit_code == 0
        assert "No adapter for 'triage-agent'" in " ".join(result.output.split())

    def test_live_junit(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _live_project(tmp_path, {"ok": "charged twice", "renamed": "please rename"})
        result = runner.invoke(app, ["test", "--live", "--format", "junit"])
        assert result.exit_code == 1
        assert 'tests="2" failures="1"' in result.stdout


class TestCliTestExpectations:
    def _scenarios(self, tmp_path, expected: str) -> None:
        d = tmp_path / "scen"
        d.mkdir()
        (d / "s.yaml").write_text(
            "scenarios:\n"
            "  - name: billing\n"
            "    input: {message: hi}\n"
            "    expectations:\n"
            f"      triage-agent: {{category: {expected}}}\n"
        )
        config = tmp_path / "a2a-spec.yaml"
        config.write_text(config.read_text() + f'scenarios_dir: "{d}"\n')

    def test_replay_expectation_mismatch_fails(self, tmp_path) -> None:
        config = _struct_project(tmp_path, {"billing": {"category": "general"}})
        self._scenarios(tmp_path, "billing")
        result = runner.invoke(app, ["test", "--config", str(config)])
        assert result.exit_code == 1, result.output
        assert "expectations FAIL" in result.output
        assert "expected 'category' = 'billing', got 'general'" in result.output

    def test_replay_expectation_match_passes(self, tmp_path) -> None:
        config = _struct_project(tmp_path, {"billing": {"category": "billing"}})
        self._scenarios(tmp_path, "billing")
        result = runner.invoke(app, ["test", "--config", str(config)])
        assert result.exit_code == 0, result.output

    def test_expectations_in_junit(self, tmp_path) -> None:
        config = _struct_project(tmp_path, {"billing": {"category": "general"}})
        self._scenarios(tmp_path, "billing")
        result = runner.invoke(app, ["test", "--config", str(config), "--format", "junit"])
        assert "expectation: expected 'category' = 'billing', got 'general'" in result.stdout

    def test_live_expectations(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _live_project(tmp_path, {"ok": "charged twice"})
        scen = tmp_path / "a2a_spec" / "scenarios" / "s.yaml"
        scen.write_text(
            scen.read_text() + "    expectations:\n      triage-agent: {category: shipping}\n"
        )
        result = runner.invoke(app, ["test", "--live"])
        assert result.exit_code == 1
        assert "expected 'category' = 'shipping', got 'billing'" in result.output

    def test_github_annotation_path_relative_to_workspace(self, tmp_path, monkeypatch) -> None:
        config = _struct_project(tmp_path, OUTPUTS)
        monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path.parent))
        result = runner.invoke(app, ["test", "--config", str(config), "--format", "github"])
        expected = f"::error file={tmp_path.name}/specs/triage.yaml,line=1,"
        assert any(line.startswith(expected) for line in result.stdout.splitlines()), result.stdout
