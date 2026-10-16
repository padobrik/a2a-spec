"""Tests for the core API: load_snapshots and check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_handshake import CheckResult, check, load_snapshots
from agent_handshake.exceptions import ConfigError, SnapshotFormatError
from agent_handshake.spec.schema import Spec, StructuralSpec

SPEC = Spec(
    name="t2r",
    version="1.0",
    producer="triage",
    consumer="resolution",
    structural=StructuralSpec(required=["category"]),
)


def _write(root: Path, agent: str, scenario: str, output: dict[str, object]) -> Path:
    path = root / agent / f"{scenario}_abc.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1,
        "fingerprint": "abc",
        "agent_id": agent,
        "scenario": scenario,
        "input": {"message": "m"},
        "output": output,
    }
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def snapshots_dir(tmp_path: Path) -> Path:
    _write(tmp_path, "triage", "shipping", {"category": "shipping"})
    _write(tmp_path, "triage", "billing", {"category": "billing"})
    _write(tmp_path, "resolution", "billing", {"reply": "ok"})
    return tmp_path


class TestLoadSnapshots:
    def test_directory_is_sorted_by_agent_and_scenario(self, snapshots_dir: Path) -> None:
        loaded = load_snapshots(snapshots_dir)
        assert [(s.fingerprint.agent_id, s.scenario) for s in loaded] == [
            ("resolution", "billing"),
            ("triage", "billing"),
            ("triage", "shipping"),
        ]

    def test_agent_directory(self, snapshots_dir: Path) -> None:
        assert [s.scenario for s in load_snapshots(snapshots_dir / "triage")] == [
            "billing",
            "shipping",
        ]

    def test_single_file(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "triage", "billing", {"category": "billing"})
        [snapshot] = load_snapshots(path)
        assert snapshot.output_data == {"category": "billing"}

    def test_missing_source(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="Snapshot source not found"):
            load_snapshots(tmp_path / "nope")

    def test_broken_file_names_it(self, snapshots_dir: Path) -> None:
        (snapshots_dir / "triage" / "broken_x.json").write_text("{")
        with pytest.raises(SnapshotFormatError, match=r"broken_x\.json is not valid JSON"):
            load_snapshots(snapshots_dir)


class TestCheck:
    def test_checks_only_the_producer(self, snapshots_dir: Path) -> None:
        result = check(SPEC, load_snapshots(snapshots_dir))
        assert isinstance(result, CheckResult)
        assert result.passed
        assert [c.snapshot.scenario for c in result.cases] == ["billing", "shipping"]

    def test_violation(self, tmp_path: Path) -> None:
        _write(tmp_path, "triage", "renamed", {"issue_type": "billing"})
        result = check(SPEC, load_snapshots(tmp_path))
        assert not result.passed
        [case] = result.failed
        assert case.failures == ["structural: [<root>] 'category' is a required property"]

    def test_expected_values(self, snapshots_dir: Path) -> None:
        result = check(SPEC, load_snapshots(snapshots_dir), {"billing": {"category": "general"}})
        assert [c.snapshot.scenario for c in result.failed] == ["billing"]
        assert "expected 'category' = 'general', got 'billing'" in result.failed[0].failures[0]

    def test_no_snapshots_is_an_error_not_a_pass(self, tmp_path: Path) -> None:
        _write(tmp_path, "resolution", "billing", {"reply": "ok"})
        result = check(SPEC, load_snapshots(tmp_path))
        assert not result.passed
        assert result.cases == []
        assert result.errors == [
            "No snapshots for 'triage', the producer of spec 't2r'. "
            "Record them with 'handshake record'."
        ]

    def test_same_input_same_result(self, snapshots_dir: Path) -> None:
        first = check(SPEC, load_snapshots(snapshots_dir))
        second = check(SPEC, load_snapshots(snapshots_dir))
        assert [(c.snapshot.scenario, c.failures) for c in first.cases] == [
            (c.snapshot.scenario, c.failures) for c in second.cases
        ]
