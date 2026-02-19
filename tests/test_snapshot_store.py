"""Tests for snapshot storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from a2a_spec.exceptions import SnapshotNotFoundError
from a2a_spec.snapshot.fingerprint import Fingerprint
from a2a_spec.snapshot.store import Snapshot, SnapshotStore


class TestSnapshotStore:
    """Tests for file-based snapshot storage."""

    def test_save_and_load(self, tmp_store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Round-trip save then load must return identical data."""
        tmp_store.save(sample_snapshot)
        loaded = tmp_store.load("triage-agent", "billing_overcharge")
        assert loaded.output_data == sample_snapshot.output_data
        assert loaded.scenario == "billing_overcharge"

    def test_load_missing_agent_raises(self, tmp_store: SnapshotStore) -> None:
        """Loading a snapshot for an unknown agent must raise SnapshotNotFoundError."""
        with pytest.raises(SnapshotNotFoundError, match="no-agent"):
            tmp_store.load("no-agent", "any-scenario")

    def test_load_missing_scenario_raises(
        self, tmp_store: SnapshotStore, sample_snapshot: Snapshot
    ) -> None:
        """Loading a snapshot for an unknown scenario must raise SnapshotNotFoundError."""
        tmp_store.save(sample_snapshot)
        with pytest.raises(SnapshotNotFoundError, match="nonexistent"):
            tmp_store.load("triage-agent", "nonexistent")

    def test_exists_returns_true(self, tmp_store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """exists() must return True after saving a snapshot."""
        tmp_store.save(sample_snapshot)
        assert tmp_store.exists("triage-agent", "billing_overcharge")

    def test_exists_returns_false(self, tmp_store: SnapshotStore) -> None:
        """exists() must return False for an unknown agent/scenario."""
        assert not tmp_store.exists("no-agent", "no-scenario")

    def test_list_agents(self, tmp_store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """list_agents() must include the agent after saving a snapshot."""
        tmp_store.save(sample_snapshot)
        agents = tmp_store.list_agents()
        assert "triage-agent" in agents

    def test_list_agents_empty(self, tmp_store: SnapshotStore) -> None:
        """list_agents() must return an empty list when no snapshots exist."""
        assert tmp_store.list_agents() == []

    def test_list_scenarios(self, tmp_store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """list_scenarios() must include the scenario after saving a snapshot."""
        tmp_store.save(sample_snapshot)
        scenarios = tmp_store.list_scenarios("triage-agent")
        assert "billing_overcharge" in scenarios

    def test_list_scenarios_empty_for_unknown_agent(self, tmp_store: SnapshotStore) -> None:
        """list_scenarios() must return empty list for unknown agent."""
        assert tmp_store.list_scenarios("nonexistent") == []

    def test_load_all(self, tmp_store: SnapshotStore) -> None:
        """load_all() must return all saved snapshots for an agent."""
        for scenario in ["s1", "s2", "s3"]:
            fp = Fingerprint.create("agent-x", {"q": scenario})
            snap = Snapshot(fp, scenario, {"q": scenario}, {"a": scenario})
            tmp_store.save(snap)
        all_snaps = tmp_store.load_all("agent-x")
        assert len(all_snaps) == 3

    def test_load_all_empty(self, tmp_store: SnapshotStore) -> None:
        """load_all() must return empty list when no snapshots exist."""
        assert tmp_store.load_all("nonexistent") == []

    def test_snapshot_serialization(self, sample_snapshot: Snapshot) -> None:
        """to_dict() / from_dict() round-trip must preserve all data."""
        d = sample_snapshot.to_dict()
        assert d["agent_id"] == "triage-agent"
        assert d["scenario"] == "billing_overcharge"
        restored = Snapshot.from_dict(d)
        assert restored.output_data == sample_snapshot.output_data

    def test_save_creates_nested_directory(self, tmp_path: Path) -> None:
        """save() must create the agent directory if it does not exist."""
        store = SnapshotStore(tmp_path / "deep" / "nested" / "dir")
        fp = Fingerprint.create("agent-a", {"x": 1})
        snap = Snapshot(fp, "s1", {"x": 1}, {"y": 2})
        path = store.save(snap)
        assert path.exists()

    def test_snapshot_full_roundtrip(
        self, tmp_store: SnapshotStore, sample_snapshot: Snapshot
    ) -> None:
        """Save then load must produce identical input_data and output_data."""
        tmp_store.save(sample_snapshot)
        loaded = tmp_store.load(
            sample_snapshot.fingerprint.agent_id,
            sample_snapshot.scenario,
        )
        assert loaded.output_data == sample_snapshot.output_data
        assert loaded.input_data == sample_snapshot.input_data
        assert loaded.scenario == sample_snapshot.scenario


class TestSnapshotStorePathTraversal:
    """Security tests for path traversal protection."""

    def test_rejects_dotdot_in_agent_id(self, tmp_store: SnapshotStore) -> None:
        """agent_id containing '..' must be rejected."""
        fp = Fingerprint(agent_id="../etc", input_hash="abc")
        snap = Snapshot(
            fingerprint=fp,
            scenario="test",
            input_data={},
            output_data={},
        )
        with pytest.raises(ValueError, match="unsafe"):
            tmp_store.save(snap)

    def test_rejects_slash_in_agent_id(self, tmp_store: SnapshotStore) -> None:
        """agent_id containing '/' must be rejected."""
        fp = Fingerprint(agent_id="a/b", input_hash="abc")
        snap = Snapshot(
            fingerprint=fp,
            scenario="test",
            input_data={},
            output_data={},
        )
        with pytest.raises(ValueError, match="unsafe"):
            tmp_store.save(snap)

    def test_rejects_dotdot_in_scenario(self, tmp_store: SnapshotStore) -> None:
        """scenario containing '..' must be rejected on save."""
        fp = Fingerprint(agent_id="valid-agent", input_hash="abc")
        snap = Snapshot(
            fingerprint=fp,
            scenario="../../etc/passwd",
            input_data={},
            output_data={},
        )
        with pytest.raises(ValueError, match="unsafe"):
            tmp_store.save(snap)

    def test_rejects_dotdot_in_load_agent_id(self, tmp_store: SnapshotStore) -> None:
        """load() must reject agent_id with path traversal."""
        with pytest.raises(ValueError, match="unsafe"):
            tmp_store.load("../etc", "scenario")

    def test_rejects_dotdot_in_load_scenario(self, tmp_store: SnapshotStore) -> None:
        """load() must reject scenario with path traversal."""
        with pytest.raises(ValueError, match="unsafe"):
            tmp_store.load("valid-agent", "../etc/passwd")

    def test_rejects_dot_prefix_agent_id(self, tmp_store: SnapshotStore) -> None:
        """agent_id starting with '.' must be rejected."""
        fp = Fingerprint(agent_id=".hidden", input_hash="abc")
        snap = Snapshot(
            fingerprint=fp,
            scenario="test",
            input_data={},
            output_data={},
        )
        with pytest.raises(ValueError, match="cannot start with"):
            tmp_store.save(snap)

    def test_rejects_empty_agent_id(self, tmp_store: SnapshotStore) -> None:
        """Empty agent_id must be rejected."""
        fp = Fingerprint(agent_id="", input_hash="abc")
        snap = Snapshot(
            fingerprint=fp,
            scenario="test",
            input_data={},
            output_data={},
        )
        with pytest.raises(ValueError, match="cannot be empty"):
            tmp_store.save(snap)

    def test_valid_names_accepted(self, tmp_store: SnapshotStore) -> None:
        """Normal agent_id and scenario with dashes/underscores must be accepted."""
        fp = Fingerprint.create("my-agent-v2", {"x": 1})
        snap = Snapshot(fp, "test_scenario_01", {"x": 1}, {"y": 2})
        path = tmp_store.save(snap)
        assert path.exists()
