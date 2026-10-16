"""Agents whose output is plain text: recorded, read, checked and diffed."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from agent_handshake.adapters.function_adapter import FunctionAdapter
from agent_handshake.cli.main import app
from agent_handshake.diff.consumers import rate_for_consumers
from agent_handshake.diff.engine import DiffEngine, DriftSeverity
from agent_handshake.snapshot.recorder import Recorder
from agent_handshake.snapshot.store import SnapshotStore, read_snapshot
from agent_handshake.spec.checker import SpecChecker
from agent_handshake.spec.schema import PolicyRule, Spec, StructuralSpec

runner = CliRunner()


def _spec(
    producer: str, structural: StructuralSpec, policy: list[PolicyRule] | None = None
) -> Spec:
    return Spec(
        name=f"{producer}-spec",
        version="1.0",
        producer=producer,
        consumer="writer",
        structural=structural,
        policy=policy or [],
    )


async def test_text_output_is_recorded_and_read(tmp_path: Path) -> None:
    async def search(data: dict) -> str:
        return f"Results for {data['q']}"

    store = SnapshotStore(tmp_path)
    adapter = FunctionAdapter(fn=search, agent_id="search", version="1")
    await Recorder(store).record(adapter, "apple", {"q": "apple"})
    (path,) = tmp_path.glob("search/*.json")
    assert json.loads(path.read_text())["output"] == "Results for apple"
    assert read_snapshot(path).output_data == "Results for apple"


class TestChecks:
    def test_object_spec_on_text_fails_clearly(self) -> None:
        check = SpecChecker().check(_spec("search", StructuralSpec(required=["q"])), "text", {})
        assert check.failures() == [
            "structural: [<root>] the output is text, but the spec expects an object"
        ]

    def test_text_spec_with_regex(self) -> None:
        rule = PolicyRule(rule="no_ids", method="regex", patterns=[r"INT-\d{6}"])
        spec = _spec("search", StructuralSpec(type="string"), [rule])
        assert SpecChecker().check(spec, "clean text", {}).passed
        failures = SpecChecker().check(spec, "see INT-123456", {}).failures()
        assert failures == ["policy no_ids: Pattern matched in the text output: 'INT-123456'"]

    def test_expectation_on_text(self) -> None:
        spec = _spec("search", StructuralSpec(type="string"))
        check = SpecChecker().check(spec, "text", {}, {"category": "billing"})
        assert check.failures() == [
            "expectation: expected 'category' = 'billing', but the output is text"
        ]


def test_cli_text_snapshot_fails_only_its_spec(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    for producer in ("search", "planner"):
        (specs / f"{producer}.yaml").write_text(
            f"spec:\n  name: {producer}-spec\n  version: '1'\n  producer: {producer}\n"
            "  consumer: writer\n  structural:\n    type: object\n    required: [q]\n"
        )
        snaps = tmp_path / "snapshots" / producer
        snaps.mkdir(parents=True)
        output = "plain text" if producer == "search" else {"q": "apple"}
        (snaps / "s_1.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "agent_id": producer,
                    "scenario": "s",
                    "input": {},
                    "output": output,
                }
            )
        )
    config = tmp_path / "handshake.yaml"
    config.write_text(
        f'project_name: t\nspecs_dir: "{specs.as_posix()}"\n'
        f'storage:\n  path: "{(tmp_path / "snapshots").as_posix()}"\n'
    )
    result = runner.invoke(app, ["test", "--config", str(config)])
    out = " ".join(result.output.split())
    assert result.exit_code == 1, result.output
    assert "the output is text, but the spec expects an object" in out
    assert "PASS planner-spec / s" in out
    assert "1 passed" in out


class TestDiff:
    def test_changed_text(self) -> None:
        (result,) = DiffEngine().diff("old text", "new text")
        assert (result.field, result.severity) == ("(output)", DriftSeverity.MEDIUM)
        assert result.explanation == "The text output changed"
        assert DiffEngine().diff("same", "same") == []

    def test_object_to_text_fails_for_every_consumer(self) -> None:
        results = DiffEngine().diff({"q": "apple"}, "apple")
        (result,) = results
        assert result.severity == DriftSeverity.CRITICAL
        assert result.explanation == "The output changed from an object to text"
        spec = _spec("search", StructuralSpec(properties={"other": {}}))
        (rated,) = rate_for_consumers(results, [spec])
        assert rated.severity == DriftSeverity.HIGH
        assert rated.explanation.endswith("spec 'search-spec' for writer names it")
