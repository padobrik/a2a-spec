"""Snapshot files: format version, clear errors for broken files, no needless rewrites."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_handshake.cli.main import app
from agent_handshake.exceptions import SnapshotFormatError
from agent_handshake.snapshot.fingerprint import Fingerprint
from agent_handshake.snapshot.store import (
    SCHEMA_VERSION,
    Snapshot,
    SnapshotStore,
    read_snapshot,
)

runner = CliRunner()

SPEC = """spec:
  name: t2r
  version: "1.0"
  producer: triage
  consumer: resolution
  structural:
    type: object
"""

GOOD = {
    "schema_version": 1,
    "fingerprint": "abc",
    "agent_id": "triage",
    "scenario": "billing",
    "input": {"message": "m"},
    "output": {"category": "billing"},
}


def _snapshot(output: dict[str, object] | None = None) -> Snapshot:
    return Snapshot(
        fingerprint=Fingerprint.create("triage", {"message": "m"}),
        scenario="billing",
        input_data={"message": "m"},
        output_data=output or {"category": "billing"},
    )


def _project(tmp_path: Path, content: str) -> Path:
    (tmp_path / "handshake" / "specs").mkdir(parents=True)
    (tmp_path / "handshake" / "specs" / "t2r.yaml").write_text(SPEC)
    snaps = tmp_path / "handshake" / "snapshots" / "triage"
    snaps.mkdir(parents=True)
    path = snaps / "billing_abc.json"
    path.write_text(content)
    (tmp_path / "handshake.yaml").write_text("project_name: t\n")
    return path


BROKEN = [
    ("{not json", "is not valid JSON (Expecting property name"),
    ("[1, 2]", "must be a JSON object"),
    (json.dumps({k: v for k, v in GOOD.items() if k != "input"}), "has no 'input' field"),
    (json.dumps({k: v for k, v in GOOD.items() if k != "output"}), "has no 'output' field"),
    (json.dumps({**GOOD, "output": 42}), "has a 'output' field that is not an object or a string"),
    (json.dumps({**GOOD, "schema_version": "1"}), "has a schema_version that is not an integer"),
    (json.dumps({**GOOD, "schema_version": None}), "has a schema_version that is not an integer"),
    (json.dumps({**GOOD, "schema_version": 0}), "has schema_version 0; versions start at 1"),
    (json.dumps({**GOOD, "schema_version": 99}), "has schema_version 99"),
]


class TestBrokenFiles:
    @pytest.mark.parametrize(("content", "problem"), BROKEN)
    def test_read_names_the_file(self, tmp_path: Path, content: str, problem: str) -> None:
        path = tmp_path / "s.json"
        path.write_text(content)
        with pytest.raises(SnapshotFormatError) as info:
            read_snapshot(path)
        assert str(info.value).startswith(f"Snapshot {path} {problem}")

    @pytest.mark.parametrize(("content", "problem"), BROKEN)
    def test_cli_test_reports_without_traceback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str, problem: str
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _project(tmp_path, content)
        result = runner.invoke(app, ["test"])
        assert result.exit_code == 2, result.output
        out = " ".join(result.output.split())
        assert "billing_abc.json" in out
        assert problem.split(" (")[0] in out
        assert "Traceback" not in result.output
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_newer_version_says_to_upgrade(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        path.write_text(json.dumps({**GOOD, "schema_version": SCHEMA_VERSION + 1}))
        with pytest.raises(SnapshotFormatError, match="Upgrade agent-handshake"):
            read_snapshot(path)

    def test_broken_file_says_how_to_fix(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        path.write_text("{}")
        with pytest.raises(SnapshotFormatError, match="Record it again with 'handshake record'"):
            read_snapshot(path)


class TestVersion:
    def test_saved_files_carry_the_version(self, tmp_path: Path) -> None:
        path = SnapshotStore(tmp_path).save(_snapshot())
        assert json.loads(path.read_text())["schema_version"] == SCHEMA_VERSION == 1

    def test_file_without_version_reads_as_version_1_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = tmp_path / "s.json"
        path.write_text(json.dumps({k: v for k, v in GOOD.items() if k != "schema_version"}))
        with caplog.at_level(logging.WARNING, logger="agent_handshake.snapshot.store"):
            snapshot = read_snapshot(path)
        assert snapshot.output_data == {"category": "billing"}
        assert f"Snapshot {path} has no schema_version; read as version 1" in caplog.text


class TestNoNeedlessRewrite:
    def _age(self, path: Path) -> int:
        os.utime(path, ns=(1_000_000_000, 1_000_000_000))
        return path.stat().st_mtime_ns

    def test_same_input_and_output_keeps_the_file(self, tmp_path: Path) -> None:
        store = SnapshotStore(tmp_path)
        path = store.save(_snapshot())
        before = path.read_bytes()
        mtime = self._age(path)
        store.save(_snapshot())  # a new timestamp and metadata, same content
        assert path.stat().st_mtime_ns == mtime
        assert path.read_bytes() == before

    def test_change_of_json_type_rewrites(self, tmp_path: Path) -> None:
        store = SnapshotStore(tmp_path)
        path = store.save(_snapshot({"value": 1}))
        store.save(_snapshot({"value": True}))
        # Python treats 1 == True, so compare the JSON text.
        assert json.dumps(json.loads(path.read_text())["output"]) == '{"value": true}'

    def test_changed_output_rewrites(self, tmp_path: Path) -> None:
        store = SnapshotStore(tmp_path)
        path = store.save(_snapshot())
        store.save(_snapshot({"category": "shipping"}))
        assert json.loads(path.read_text())["output"] == {"category": "shipping"}

    def test_file_without_version_is_rewritten_with_it(self, tmp_path: Path) -> None:
        store = SnapshotStore(tmp_path)
        path = store.save(_snapshot())
        data = json.loads(path.read_text())
        del data["schema_version"]
        path.write_text(json.dumps(data))
        store.save(_snapshot())
        assert json.loads(path.read_text())["schema_version"] == 1
