"""Tests for pipeline executor."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_handshake.exceptions import PipelineExecutionError
from agent_handshake.pipeline.dag import Edge, PipelineDAG
from agent_handshake.pipeline.executor import PipelineExecutor
from agent_handshake.snapshot.fingerprint import Fingerprint
from agent_handshake.snapshot.replay import ReplayEngine
from agent_handshake.snapshot.store import Snapshot, SnapshotStore


class TestPipelineExecutor:
    @pytest.fixture
    def simple_dag(self) -> PipelineDAG:
        return PipelineDAG(
            name="simple",
            agents=["agent-a", "agent-b"],
            edges=[Edge("agent-a", "agent-b")],
        )

    @pytest.fixture
    def store_with_snapshots(self, tmp_path: Path) -> SnapshotStore:
        store = SnapshotStore(tmp_path / "snapshots")
        for agent_id in ["agent-a", "agent-b"]:
            fp = Fingerprint.create(agent_id, {"msg": "test"})
            snap = Snapshot(fp, "scenario1", {"msg": "test"}, {"result": f"{agent_id}-output"})
            store.save(snap)
        return store

    async def test_replay_execution(
        self, simple_dag: PipelineDAG, store_with_snapshots: SnapshotStore
    ) -> None:
        replay = ReplayEngine(store_with_snapshots)
        executor = PipelineExecutor(dag=simple_dag, replay_engine=replay)
        trace = await executor.execute("scenario1", {"msg": "test"}, mode="replay")
        assert len(trace.steps) == 2
        assert trace.path == ["agent-a", "agent-b"]

    async def test_replay_without_engine_raises(self, simple_dag: PipelineDAG) -> None:
        executor = PipelineExecutor(dag=simple_dag)
        with pytest.raises(PipelineExecutionError, match="ReplayEngine"):
            await executor.execute("scenario1", {}, mode="replay")

    async def test_live_without_adapter_raises(self, simple_dag: PipelineDAG) -> None:
        executor = PipelineExecutor(dag=simple_dag)
        with pytest.raises(PipelineExecutionError, match="No adapter"):
            await executor.execute("scenario1", {}, mode="live")

    async def test_trace_latency(
        self, simple_dag: PipelineDAG, store_with_snapshots: SnapshotStore
    ) -> None:
        replay = ReplayEngine(store_with_snapshots)
        executor = PipelineExecutor(dag=simple_dag, replay_engine=replay)
        trace = await executor.execute("scenario1", {"msg": "test"}, mode="replay")
        assert trace.total_latency_ms >= 0

    async def test_trace_summary(
        self, simple_dag: PipelineDAG, store_with_snapshots: SnapshotStore
    ) -> None:
        replay = ReplayEngine(store_with_snapshots)
        executor = PipelineExecutor(dag=simple_dag, replay_engine=replay)
        trace = await executor.execute("scenario1", {"msg": "test"}, mode="replay")
        summary = trace.summary()
        assert "simple" in summary
        assert "scenario1" in summary
