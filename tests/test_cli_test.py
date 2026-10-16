"""Tests for CLI test command."""

from __future__ import annotations

from typer.testing import CliRunner

from agent_handshake.cli.main import app

runner = CliRunner()


class TestCliTest:
    def test_test_help(self) -> None:
        result = runner.invoke(app, ["test", "--help"])
        assert result.exit_code == 0
        assert "replay" in result.output.lower() or "spec" in result.output.lower()

    def test_test_no_specs_dir(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "handshake.yaml"
        config.write_text('project_name: test\nspecs_dir: "./nonexistent"')
        result = runner.invoke(app, ["test", "--config", str(config)])
        assert result.exit_code != 0

    def test_test_empty_specs(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        specs = tmp_path / "specs"
        specs.mkdir()
        config = tmp_path / "handshake.yaml"
        config.write_text(f'project_name: test\nspecs_dir: "{specs.as_posix()}"')
        result = runner.invoke(app, ["test", "--config", str(config)])
        assert result.exit_code == 2

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.9.0" in result.output


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
    config = tmp_path / "handshake.yaml"
    config.write_text(
        f'project_name: demo\nspecs_dir: "{specs.as_posix()}"\n'
        f'storage:\n  path: "{(tmp_path / "snapshots").as_posix()}"\n'
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
        assert suite.get("tests") == "2"
        assert suite.get("failures") == "1"
        [failure] = suite.iter("failure")
        assert "'category' is a required property" in failure.get("message", "")
        names = {tc.get("name"): tc.get("classname") for tc in suite.iter("testcase")}
        assert names == {"billing": "triage-to-resolution", "renamed": "triage-to-resolution"}

    def test_markdown_report(self, tmp_path) -> None:
        config = _struct_project(tmp_path, OUTPUTS)
        result = runner.invoke(app, ["test", "--config", str(config), "--format", "markdown"])
        assert result.exit_code == 1
        assert result.stdout.startswith("# agent-handshake Report: demo")
        assert "**1/2 passed** | 1 failed" in result.stdout
        assert "### triage-to-resolution / renamed" in result.stdout
        assert "Spec:" not in result.stdout

    def test_github_annotations(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("GITHUB_WORKSPACE", raising=False)
        config = _struct_project(tmp_path, OUTPUTS)
        result = runner.invoke(app, ["test", "--config", str(config), "--format", "github"])
        assert result.exit_code == 1
        lines = [line for line in result.stdout.splitlines() if line.startswith("::error")]
        assert len(lines) == 1
        # Workflow command properties escape ':' and ',' (a Windows drive letter has one).
        spec_path = str(tmp_path / "specs" / "triage.yaml").replace(":", "%3A")
        assert lines[0].startswith(
            f"::error file={spec_path},line=1,title=agent-handshake triage-to-resolution::"
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
from agent_handshake import FunctionAdapter

async def triage(data):
    if "boom" in data["message"]:
        raise RuntimeError("model down")
    key = "issue_type" if "rename" in data["message"] else "category"
    return {key: "billing"}

ADAPTERS = {"triage-agent": FunctionAdapter(fn=triage, agent_id="triage-agent", version="1")}
"""


def _live_project(tmp_path, messages: dict[str, str], adapters: str = LIVE_ADAPTERS):
    specs = tmp_path / "handshake" / "specs"
    specs.mkdir(parents=True)
    (specs / "triage.yaml").write_text(STRUCT_SPEC)
    pkg = tmp_path / "handshake" / "adapters"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(adapters)
    scenarios = tmp_path / "handshake" / "scenarios"
    scenarios.mkdir()
    body = "".join(
        f"  - name: {name}\n    input:\n      message: {msg}\n" for name, msg in messages.items()
    )
    (scenarios / "s.yaml").write_text("scenarios:\n" + body)
    (tmp_path / "handshake.yaml").write_text("project_name: demo\n")


class TestCliTestLive:
    def test_live_checks_producer_output_without_snapshots(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _live_project(tmp_path, {"ok": "charged twice", "renamed": "please rename"})
        result = runner.invoke(app, ["test", "--live"])
        assert result.exit_code == 1, result.output
        assert "PASS triage-to-resolution / ok" in result.output
        assert "FAIL triage-to-resolution / renamed" in result.output
        assert "'category' is a required property" in result.output
        assert not (tmp_path / "handshake" / "snapshots").exists()

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
        assert "agent call failed: " in result.output
        assert "model down" in result.output

    def test_producer_without_adapter_is_an_error(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _live_project(tmp_path, {"ok": "charged twice"}, adapters="ADAPTERS = {}\n")
        result = runner.invoke(app, ["test", "--live"])
        assert result.exit_code == 2
        assert "No adapter for 'triage-agent'" in " ".join(result.output.split())

    def test_live_skips_scenarios_for_other_agents(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _live_project(tmp_path, {"ok": "charged twice", "renamed": "please rename"})
        scen = tmp_path / "handshake" / "scenarios" / "s.yaml"
        scen.write_text(scen.read_text() + "    agents: [resolution-agent]\n")
        result = runner.invoke(app, ["test", "--live"])
        assert result.exit_code == 0, result.output
        assert "PASS triage-to-resolution / ok" in result.output
        assert "renamed" not in result.output

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
        config = tmp_path / "handshake.yaml"
        config.write_text(config.read_text() + f'scenarios_dir: "{d.as_posix()}"\n')

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
        scen = tmp_path / "handshake" / "scenarios" / "s.yaml"
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


CUSTOM_POLICY_SPEC = """
spec:
  name: reply-policy
  version: "1.0"
  producer: support-agent
  consumer: user
  structural:
    type: object
  policy:
    - rule: no_refund_promise
      method: custom
      validator: cli_shop_checks.no_refund_promise
"""


class TestCliTestCustomPolicy:
    def test_validator_from_project_module(self, tmp_path, monkeypatch) -> None:
        import json
        import sys

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "path", [p for p in sys.path if p not in ("", str(tmp_path))])
        monkeypatch.delitem(sys.modules, "cli_shop_checks", raising=False)
        (tmp_path / "cli_shop_checks.py").write_text(
            "def no_refund_promise(output, input_data):\n"
            "    ok = 'refund' not in output['reply']\n"
            "    return ok, '' if ok else 'reply promises a refund'\n"
        )
        specs = tmp_path / "handshake" / "specs"
        specs.mkdir(parents=True)
        (specs / "reply.yaml").write_text(CUSTOM_POLICY_SPEC)
        snaps = tmp_path / "handshake" / "snapshots" / "support-agent"
        snaps.mkdir(parents=True)
        for name, reply in (("calm", "We are checking."), ("promise", "We will refund you.")):
            (snaps / f"{name}_abc.json").write_text(
                json.dumps(
                    {
                        "fingerprint": "abc",
                        "agent_id": "support-agent",
                        "scenario": name,
                        "input": {},
                        "output": {"reply": reply},
                    }
                )
            )
        result = runner.invoke(app, ["test"])
        out = " ".join(result.output.split())
        assert result.exit_code == 1, result.output
        assert "PASS reply-policy / calm" in out
        assert "FAIL reply-policy / promise" in out
        assert "reply promises a refund" in out
