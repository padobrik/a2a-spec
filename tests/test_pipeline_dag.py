"""Tests for pipeline DAG building and validation."""

from __future__ import annotations

import pytest

from a2a_spec.exceptions import ConfigError
from a2a_spec.pipeline.dag import Edge, PipelineDAG, build_dag


class TestPipelineDAG:
    def test_topological_order_linear(self) -> None:
        dag = PipelineDAG(
            name="test",
            agents=["a", "b", "c"],
            edges=[Edge("a", "b"), Edge("b", "c")],
        )
        order = dag.topological_order()
        assert order == ["a", "b", "c"]

    def test_entry_agents(self) -> None:
        dag = PipelineDAG(
            name="test",
            agents=["a", "b", "c"],
            edges=[Edge("a", "b"), Edge("a", "c")],
        )
        assert dag.entry_agents() == ["a"]

    def test_exit_agents(self) -> None:
        dag = PipelineDAG(
            name="test",
            agents=["a", "b", "c"],
            edges=[Edge("a", "b"), Edge("a", "c")],
        )
        assert set(dag.exit_agents()) == {"b", "c"}

    def test_cycle_detection(self) -> None:
        dag = PipelineDAG(
            name="cyclic",
            agents=["a", "b"],
            edges=[Edge("a", "b"), Edge("b", "a")],
        )
        with pytest.raises(ConfigError, match="cycle"):
            dag.topological_order()

    def test_validate_unknown_agent(self) -> None:
        dag = PipelineDAG(
            name="test",
            agents=["a"],
            edges=[Edge("a", "unknown")],
        )
        errors = dag.validate()
        assert any("unknown" in e for e in errors)

    def test_successors(self) -> None:
        dag = PipelineDAG(
            name="test",
            agents=["a", "b", "c"],
            edges=[Edge("a", "b"), Edge("a", "c")],
        )
        succ = dag.successors("a")
        assert len(succ) == 2

    def test_predecessors(self) -> None:
        dag = PipelineDAG(
            name="test",
            agents=["a", "b", "c"],
            edges=[Edge("a", "c"), Edge("b", "c")],
        )
        pred = dag.predecessors("c")
        assert len(pred) == 2


class TestBuildDag:
    def test_build_from_spec(self) -> None:
        spec = {
            "name": "support-pipeline",
            "agents": {"triage": {}, "resolution": {}},
            "edges": [{"from": "triage", "to": "resolution"}],
        }
        dag = build_dag(spec)
        assert dag.name == "support-pipeline"
        assert len(dag.agents) == 2

    def test_build_invalid_pipeline_raises(self) -> None:
        spec = {
            "name": "bad",
            "agents": {"a": {}},
            "edges": [{"from": "a", "to": "unknown"}],
        }
        with pytest.raises(ConfigError, match="Invalid pipeline"):
            build_dag(spec)
