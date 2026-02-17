"""Tests for snapshot replay engine."""

from __future__ import annotations

import pytest

from a2a_spec.exceptions import SnapshotNotFoundError
from a2a_spec.snapshot.replay import ReplayEngine
from a2a_spec.snapshot.store import Snapshot, SnapshotStore


class TestReplayEngine:
    def test_replay_returns_output(
        self, tmp_store: SnapshotStore, sample_snapshot: Snapshot
    ) -> None:
        tmp_store.save(sample_snapshot)
        engine = ReplayEngine(tmp_store)
        output = engine.replay("triage-agent", "billing_overcharge")
        assert output["category"] == "billing"
        assert output["confidence"] == 0.95

    def test_replay_missing_raises(self, tmp_store: SnapshotStore) -> None:
        engine = ReplayEngine(tmp_store)
        with pytest.raises(SnapshotNotFoundError):
            engine.replay("no-agent", "no-scenario")

    def test_replay_snapshot_returns_full_object(
        self, tmp_store: SnapshotStore, sample_snapshot: Snapshot
    ) -> None:
        tmp_store.save(sample_snapshot)
        engine = ReplayEngine(tmp_store)
        snap = engine.replay_snapshot("triage-agent", "billing_overcharge")
        assert snap.input_data == {"message": "I was charged twice"}
        assert snap.output_data["category"] == "billing"

    def test_has_snapshot_true(self, tmp_store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        tmp_store.save(sample_snapshot)
        engine = ReplayEngine(tmp_store)
        assert engine.has_snapshot("triage-agent", "billing_overcharge")

    def test_has_snapshot_false(self, tmp_store: SnapshotStore) -> None:
        engine = ReplayEngine(tmp_store)
        assert not engine.has_snapshot("no-agent", "no-scenario")

    def test_replay_is_deterministic(
        self, tmp_store: SnapshotStore, sample_snapshot: Snapshot
    ) -> None:
        tmp_store.save(sample_snapshot)
        engine = ReplayEngine(tmp_store)
        out1 = engine.replay("triage-agent", "billing_overcharge")
        out2 = engine.replay("triage-agent", "billing_overcharge")
        assert out1 == out2
