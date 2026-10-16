"""Tests for the pytest plugin, run through real pytest sessions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

SPEC = """
spec:
  name: triage-to-resolution
  version: "1.0"
  producer: triage-agent
  consumer: resolution-agent
  structural:
    type: object
    required: [category]
    properties:
      category: {type: string}
"""


def _snapshot(pytester: pytest.Pytester, scenario: str, output: dict[str, object]) -> None:
    snaps = pytester.path / "handshake" / "snapshots" / "triage-agent"
    snaps.mkdir(parents=True, exist_ok=True)
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


@pytest.fixture
def project(pytester: pytest.Pytester) -> pytest.Pytester:
    specs = pytester.path / "handshake" / "specs"
    specs.mkdir(parents=True)
    (specs / "triage.yaml").write_text(SPEC)
    pytester.makefile(
        ".yaml",
        handshake='specs_dir: "handshake/specs"\nstorage:\n  path: "handshake/snapshots"\n',
    )
    _snapshot(pytester, "billing", {"category": "billing"})
    return pytester


def _move_to_subproject(pytester: pytest.Pytester) -> Path:
    """Move the project into app/ under a rootdir that has only a pytest.ini."""
    app = pytester.mkdir("app")
    for name in ("handshake.yaml", "handshake"):
        (pytester.path / name).rename(app / name)
    pytester.makeini("[pytest]\n")
    return app


class TestPytestPlugin:
    def test_inert_without_handshake_yaml(self, project: pytest.Pytester) -> None:
        (project.path / "handshake.yaml").unlink()
        result = project.runpytest("handshake/specs")
        result.assert_outcomes()
        assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED

    def test_enabled_by_handshake_yaml_in_rootdir(self, project: pytest.Pytester) -> None:
        result = project.runpytest("handshake/specs")
        result.assert_outcomes(passed=1)

    def test_nearest_handshake_yaml_below_rootdir(
        self, project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = _move_to_subproject(project)
        monkeypatch.chdir(app / "handshake")
        result = project.runpytest()
        result.assert_outcomes(passed=1)

    def test_nearest_handshake_yaml_wins(
        self, project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = _move_to_subproject(project)
        other = project.mkdir("other_specs")
        (other / "orphan.yaml").write_text(SPEC.replace("triage-agent", "nobody"))
        project.makefile(".yaml", handshake='specs_dir: "other_specs"\n')
        monkeypatch.chdir(app)
        result = project.runpytest()
        result.assert_outcomes(passed=1)

    def test_handshake_yaml_above_rootdir_ignored(
        self, project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = project.mkdir("app")
        (app / "pytest.ini").write_text("[pytest]\n")
        monkeypatch.chdir(app)
        result = project.runpytest()
        assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED

    def test_disabled_with_p_no_handshake(self, project: pytest.Pytester) -> None:
        result = project.runpytest("-p", "no:handshake", "handshake/specs")
        assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED

    def test_disabled_by_ini_option(self, project: pytest.Pytester) -> None:
        project.makeini("[pytest]\nhandshake_enabled = false\n")
        result = project.runpytest("handshake/specs")
        assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED

    def test_specs_collected_next_to_testpaths(self, project: pytest.Pytester) -> None:
        project.makeini("[pytest]\ntestpaths = tests\n")
        project.mkdir("tests").joinpath("test_ok.py").write_text("def test_ok():\n    pass\n")
        result = project.runpytest("-v")
        result.assert_outcomes(passed=2)
        result.stdout.fnmatch_lines(["*triage.yaml::billing PASSED*"])

    def test_named_paths_are_left_alone(self, project: pytest.Pytester) -> None:
        project.mkdir("tests").joinpath("test_ok.py").write_text("def test_ok():\n    pass\n")
        result = project.runpytest("tests/test_ok.py")
        result.assert_outcomes(passed=1)

    def test_snapshots_become_tests(self, project: pytest.Pytester) -> None:
        _snapshot(project, "shipping", {"category": "shipping"})
        result = project.runpytest("--handshake", "handshake/specs", "-v")
        result.assert_outcomes(passed=2)
        result.stdout.fnmatch_lines(
            ["*triage.yaml::billing PASSED*", "*triage.yaml::shipping PASSED*"]
        )

    def test_violation_fails_with_readable_message(self, project: pytest.Pytester) -> None:
        _snapshot(project, "renamed", {"issue_type": "billing"})
        result = project.runpytest("--handshake", "handshake/specs")
        result.assert_outcomes(passed=1, failed=1)
        result.stdout.fnmatch_lines(
            [
                "*contract 'triage-to-resolution' violated:*",
                "*structural: ?<root>? 'category' is a required property*",
            ]
        )

    def test_ini_option_enables(self, project: pytest.Pytester) -> None:
        project.makeini("[pytest]\nhandshake_config = handshake.yaml\n")
        result = project.runpytest("handshake/specs")
        result.assert_outcomes(passed=1)

    def test_k_selects_scenario(self, project: pytest.Pytester) -> None:
        _snapshot(project, "shipping", {"category": "shipping"})
        result = project.runpytest("--handshake", "handshake/specs", "-k", "shipping")
        result.assert_outcomes(passed=1, deselected=1)

    def test_missing_snapshots_fail(self, project: pytest.Pytester) -> None:
        other = SPEC.replace("triage-agent", "ghost-agent").replace("triage-to", "ghost-to")
        (project.path / "handshake" / "specs" / "ghost.yaml").write_text(other)
        result = project.runpytest("--handshake", "handshake/specs")
        result.assert_outcomes(passed=1, failed=1)
        result.stdout.fnmatch_lines(["*No snapshots for 'ghost-agent', the producer of spec*"])

    def test_yaml_outside_specs_dir_ignored(self, project: pytest.Pytester) -> None:
        (project.path / "other.yaml").write_text("not: a spec\n")
        result = project.runpytest("--handshake")
        result.assert_outcomes(passed=1)

    def test_handshake_check_fixture(self, project: pytest.Pytester) -> None:
        project.makepyfile(
            test_live="""
            import pytest

            def test_good(handshake_check):
                result = handshake_check("triage-to-resolution", {"category": "billing"})
                assert result.passed

            def test_bad(handshake_check):
                handshake_check("triage-to-resolution", {"issue_type": "billing"})

            def test_unknown(handshake_check):
                handshake_check("nope", {})
            """
        )
        result = project.runpytest("--handshake", "test_live.py")
        result.assert_outcomes(passed=1, failed=2)
        result.stdout.fnmatch_lines(
            ["*'category' is a required property*", "*unknown spec 'nope'*"], consecutive=False
        )

    def test_handshake_check_without_plugin_fails_clearly(self, project: pytest.Pytester) -> None:
        project.makeini("[pytest]\nhandshake_enabled = false\n")
        project.makepyfile(test_live="def test_x(handshake_check):\n    pass\n")
        result = project.runpytest("test_live.py")
        result.assert_outcomes(errors=1)
        result.stdout.fnmatch_lines(["*needs the agent-handshake plugin enabled*"])

    def test_ini_paths_relative_to_ini_file(
        self, project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project.makeini("[pytest]\nhandshake_config = handshake.yaml\n")
        monkeypatch.chdir(project.mkdir("sub"))
        result = project.runpytest(str(project.path / "handshake" / "specs"))
        result.assert_outcomes(passed=1)

    def test_cli_config_relative_to_working_dir(
        self, project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nested = project.mkdir("nested")
        (project.path / "handshake.yaml").rename(nested / "handshake.yaml")
        result = project.runpytest("--handshake-config", "nested/handshake.yaml", "handshake/specs")
        result.assert_outcomes(passed=1)

    def test_consumer_code_item_for_inferred_spec(self, project: pytest.Pytester) -> None:
        consumer = project.path / "res.py"
        consumer.write_text("def run(data):\n    return data['category']\n")
        spec = project.path / "handshake" / "specs" / "triage.yaml"
        spec.write_text(
            SPEC.replace(
                "  consumer: resolution-agent\n",
                f"  consumer: resolution-agent\n  inferred_from: {consumer}:run\n",
            )
        )
        result = project.runpytest("--handshake", "handshake/specs", "-v")
        result.assert_outcomes(passed=2)
        result.stdout.fnmatch_lines(["*triage.yaml::consumer_code PASSED*"])

        consumer.write_text("def run(data):\n    return data['category'], data['urgency']\n")
        result = project.runpytest("--handshake", "handshake/specs")
        result.assert_outcomes(passed=1, failed=1)
        result.stdout.fnmatch_lines(
            ["*spec 'triage-to-resolution' is out of date*", "*run reads 'urgency' (line 2)*"]
        )

    def test_scenario_expectations(self, project: pytest.Pytester) -> None:
        scen = project.path / "handshake" / "scenarios"
        scen.mkdir()
        (scen / "s.yaml").write_text(
            "scenarios:\n  - name: billing\n    input: {message: hi}\n"
            "    expectations:\n      triage-agent: {category: shipping}\n"
        )
        result = project.runpytest("--handshake", "handshake/specs")
        result.assert_outcomes(failed=1)
        result.stdout.fnmatch_lines(
            ["*expectation: expected 'category' = 'shipping', got 'billing'*"]
        )


def test_broken_snapshot_fails_with_its_path(project: pytest.Pytester) -> None:
    broken = project.path / "handshake" / "snapshots" / "triage-agent" / "billing_abc123.json"
    broken.write_text("{not json")
    result = project.runpytest("--handshake", "handshake/specs")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Snapshot *billing_abc123.json is not valid JSON*"])
    result.stdout.no_fnmatch_line("*Traceback*")


def test_broken_snapshot_of_another_producer_does_not_block(project: pytest.Pytester) -> None:
    other = project.path / "handshake" / "snapshots" / "other-agent" / "x_1.json"
    other.parent.mkdir(parents=True)
    other.write_text("{not json")
    result = project.runpytest("--handshake", "handshake/specs")
    result.assert_outcomes(passed=1)
