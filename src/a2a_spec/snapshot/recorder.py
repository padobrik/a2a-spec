"""Record live agent outputs as snapshots."""

from __future__ import annotations

from typing import Any

from a2a_spec.adapters.base import AgentAdapter
from a2a_spec.snapshot.fingerprint import Fingerprint
from a2a_spec.snapshot.store import Snapshot, SnapshotStore


class Recorder:
    """Records live agent calls and stores as snapshots.

    Usage:
        recorder = Recorder(store=SnapshotStore("./snapshots"))
        snapshot = await recorder.record(
            adapter=my_agent_adapter,
            scenario="billing_overcharge",
            input_data={"message": "I was charged twice"},
        )
    """

    def __init__(self, store: SnapshotStore) -> None:
        self.store = store

    async def record(
        self,
        adapter: AgentAdapter,
        scenario: str,
        input_data: dict[str, Any],
    ) -> Snapshot:
        """Call the agent live and record the output.

        Args:
            adapter: The agent adapter to call.
            scenario: Name of the test scenario.
            input_data: Input to send to the agent.

        Returns:
            The recorded Snapshot.
        """
        metadata = adapter.get_metadata()
        response = await adapter.call(input_data)

        fingerprint = Fingerprint.create(
            agent_id=metadata.agent_id,
            input_data=input_data,
            prompt_hash=metadata.prompt_hash,
        )

        snapshot = Snapshot(
            fingerprint=fingerprint,
            scenario=scenario,
            input_data=input_data,
            output_data=response.output,
            metadata={
                "agent_version": metadata.version,
                "model": metadata.model,
                "prompt_hash": metadata.prompt_hash,
                "latency_ms": response.latency_ms,
                "token_usage": response.token_usage,
            },
        )

        self.store.save(snapshot)
        return snapshot
