"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from a2a_spec.adapters.base import AgentAdapter, AgentMetadata, AgentResponse
from a2a_spec.snapshot.fingerprint import Fingerprint
from a2a_spec.snapshot.store import Snapshot, SnapshotStore
from a2a_spec.spec.schema import PolicyRule, Spec, StructuralSpec


@pytest.fixture
def tmp_store(tmp_path: Path) -> SnapshotStore:
    """A SnapshotStore backed by a temporary directory."""
    return SnapshotStore(tmp_path / "snapshots")


@pytest.fixture
def sample_spec() -> Spec:
    """A realistic sample spec for testing."""
    return Spec(
        name="triage-to-resolution",
        version="1.0",
        producer="triage-agent",
        consumer="resolution-agent",
        structural=StructuralSpec(
            type="object",
            required=["category", "summary"],
            properties={
                "category": {
                    "type": "string",
                    "enum": ["billing", "shipping", "product", "general"],
                },
                "summary": {"type": "string", "minLength": 10},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
        ),
        policy=[
            PolicyRule(
                rule="no_pii",
                method="regex",
                patterns=[r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"],
            ),
        ],
    )


@pytest.fixture
def sample_snapshot() -> Snapshot:
    """A sample snapshot for testing."""
    fp = Fingerprint.create(
        agent_id="triage-agent",
        input_data={"message": "I was charged twice"},
    )
    return Snapshot(
        fingerprint=fp,
        scenario="billing_overcharge",
        input_data={"message": "I was charged twice"},
        output_data={
            "category": "billing",
            "summary": "Customer reports duplicate charge",
            "confidence": 0.95,
        },
    )


class MockAdapter(AgentAdapter):
    """A mock adapter for testing."""

    def __init__(
        self,
        agent_id: str = "mock-agent",
        version: str = "1.0.0",
        output: dict[str, Any] | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._version = version
        self._output = output or {"result": "mock"}

    def get_metadata(self) -> AgentMetadata:
        return AgentMetadata(agent_id=self._agent_id, version=self._version)

    async def call(self, input_data: dict[str, Any]) -> AgentResponse:
        return AgentResponse(output=self._output, latency_ms=1.0)


@pytest.fixture
def mock_adapter() -> MockAdapter:
    return MockAdapter()
