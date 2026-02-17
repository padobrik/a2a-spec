"""Tests for snapshot storage."""

from __future__ import annotations

import pytest

from a2a_spec.exceptions import SnapshotNotFoundError
from a2a_spec.snapshot.fingerprint import Fingerprint
from a2a_spec.snapshot.store import Snapshot, SnapshotStore


class TestSnapshotStore:
    def test_save_and_load(self, tmp_store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        tmp_store.save(sample_snapshot)
        loaded = tmp_store.load("triage-agent", "billing_overcharge")
        assert loaded.output_data == sample_snapshot.output_data
        assert loaded.scenario == "billing_overcharge"

    def test_load_missing_agent_raises(self, tmp_store: SnapshotStore) -> None:
        with pytest.raises(SnapshotNotFoundError, match="no-agent"):
            tmp_store.load("no-agent", "any-scenario")

    def test_load_missing_scenario_raises(
        self, tmp_store: SnapshotStore, sample_snapshot: Snapshot
    ) -> None:
        tmp_store.save(sample_snapshot)
        with pytest.raises(SnapshotNotFoundError, match="nonexistent"):
            tmp_store.load("triage-agent", "nonexistent")

    def test_exists_returns_true(self, tmp_store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        tmp_store.save(sample_snapshot)
        assert tmp_store.exists("triage-agent", "billing_overcharge")

    def test_exists_returns_false(self, tmp_store: SnapshotStore) -> None:
        assert not tmp_store.exists("no-agent", "no-scenario")

    def test_list_agents(self, tmp_store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        tmp_store.save(sample_snapshot)
        agents = tmp_store.list_agents()
        assert "triage-agent" in agents

    def test_list_agents_empty(self, tmp_store: SnapshotStore) -> None:
        assert tmp_store.list_agents() == []

    def test_list_scenarios(self, tmp_store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        tmp_store.save(sample_snapshot)
        scenarios = tmp_store.list_scenarios("triage-agent")
        assert "billing_overcharge" in scenarios

    def test_load_all(self, tmp_store: SnapshotStore) -> None:
        for scenario in ["s1", "s2", "s3"]:
            fp = Fingerprint.create("agent-x", {"q": scenario})
            snap = Snapshot(fp, scenario, {"q": scenario}, {"a": scenario})
            tmp_store.save(snap)
        all_snaps = tmp_store.load_all("agent-x")
        assert len(all_snaps) == 3

    def test_load_all_empty(self, tmp_store: SnapshotStore) -> None:
        assert tmp_store.load_all("nonexistent") == []

    def test_snapshot_serialization(self, sample_snapshot: Snapshot) -> None:
        d = sample_snapshot.to_dict()
        assert d["agent_id"] == "triage-agent"
        assert d["scenario"] == "billing_overcharge"
        restored = Snapshot.from_dict(d)
        assert restored.output_data == sample_snapshot.output_data
