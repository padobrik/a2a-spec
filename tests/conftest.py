"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from agent_handshake.adapters.base import AgentAdapter, AgentMetadata, AgentResponse
from agent_handshake.snapshot.fingerprint import Fingerprint
from agent_handshake.snapshot.store import Snapshot, SnapshotStore
from agent_handshake.spec.schema import PolicyRule, Spec, StructuralSpec


@pytest.fixture(autouse=True)
def _cli_never_crashes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CLI call ends in an exit code and a message, never in a traceback."""
    invoke = CliRunner.invoke

    def checked(self: CliRunner, *args: Any, **kwargs: Any) -> Any:
        result = invoke(self, *args, **kwargs)
        crashed = result.exception is not None and not isinstance(result.exception, SystemExit)
        assert not crashed, f"CLI raised {result.exception!r}:\n{result.output}"
        assert "Traceback" not in result.output, result.output
        return result

    monkeypatch.setattr(CliRunner, "invoke", checked)


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
