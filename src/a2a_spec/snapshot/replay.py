"""Replay recorded snapshots for deterministic testing."""

from __future__ import annotations

from typing import Any

from a2a_spec.snapshot.store import Snapshot, SnapshotStore


class ReplayEngine:
    """Replays stored snapshots instead of calling live agents.

    This is the core mechanism for deterministic CI testing.
    No LLM calls are made — the stored output is returned directly.
    """

    def __init__(self, store: SnapshotStore) -> None:
        self.store = store

    def replay(self, agent_id: str, scenario: str) -> dict[str, Any]:
        """Get the recorded output for an agent + scenario.

        Args:
            agent_id: The agent identifier.
            scenario: The scenario name.

        Returns:
            The recorded output dict.

        Raises:
            SnapshotNotFoundError: If no snapshot exists.
        """
        snapshot = self.store.load(agent_id, scenario)
        return snapshot.output_data

    def replay_snapshot(self, agent_id: str, scenario: str) -> Snapshot:
        """Get the full snapshot object for an agent + scenario.

        Args:
            agent_id: The agent identifier.
            scenario: The scenario name.

        Returns:
            The full Snapshot object including metadata.
        """
        return self.store.load(agent_id, scenario)

    def has_snapshot(self, agent_id: str, scenario: str) -> bool:
        """Check if a replay snapshot exists."""
        return self.store.exists(agent_id, scenario)
