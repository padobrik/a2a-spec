"""Local file-based snapshot storage."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from a2a_spec.exceptions import SnapshotNotFoundError
from a2a_spec.snapshot.fingerprint import Fingerprint

logger = logging.getLogger(__name__)


class Snapshot:
    """A recorded agent interaction."""

    def __init__(
        self,
        fingerprint: Fingerprint,
        scenario: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.fingerprint = fingerprint
        self.scenario = scenario
        self.input_data = input_data
        self.output_data = output_data
        self.timestamp = timestamp or datetime.now(UTC).isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize the snapshot to a dict."""
        return {
            "fingerprint": self.fingerprint.key,
            "agent_id": self.fingerprint.agent_id,
            "scenario": self.scenario,
            "timestamp": self.timestamp,
            "input": self.input_data,
            "output": self.output_data,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        """Deserialize a snapshot from a dict."""
        fp = Fingerprint(
            agent_id=data["agent_id"],
            input_hash=data.get("fingerprint", ""),
        )
        return cls(
            fingerprint=fp,
            scenario=data["scenario"],
            input_data=data["input"],
            output_data=data["output"],
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {}),
        )


class SnapshotStore:
    """File-based snapshot storage.

    Directory layout:
        base_dir/
            {agent_id}/
                {scenario}_{fingerprint_key}.json
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    @staticmethod
    def _validate_name(name: str, label: str) -> None:
        """Ensure name is safe for filesystem use.

        Prevents path traversal attacks where a malicious agent_id or
        scenario name could escape the snapshot directory.

        Args:
            name: The name to validate (agent_id or scenario).
            label: Human-readable label used in error messages.

        Raises:
            ValueError: If name is empty, contains path-traversal characters,
                        or starts with a dot.
        """
        if not name:
            raise ValueError(f"{label} cannot be empty")
        if ".." in name or "/" in name or "\\" in name:
            raise ValueError(
                f"{label} contains unsafe characters: '{name}'. "
                f"Names must not contain '..', '/', or '\\'."
            )
        if name.startswith("."):
            raise ValueError(f"{label} cannot start with '.': '{name}'")

    def save(self, snapshot: Snapshot) -> Path:
        """Save a snapshot to disk.

        Args:
            snapshot: The snapshot to save.

        Returns:
            Path to the saved file.

        Raises:
            ValueError: If agent_id or scenario contains unsafe characters.
        """
        self._validate_name(snapshot.fingerprint.agent_id, "agent_id")
        self._validate_name(snapshot.scenario, "scenario")

        agent_dir = self.base_dir / snapshot.fingerprint.agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{snapshot.scenario}_{snapshot.fingerprint.key}.json"
        filepath = agent_dir / filename

        filepath.write_text(
            json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("Saved snapshot to %s", filepath)
        logger.info("Saved snapshot for %s/%s", snapshot.fingerprint.agent_id, snapshot.scenario)
        return filepath

    def load(self, agent_id: str, scenario: str) -> Snapshot:
        """Load the latest snapshot for an agent + scenario.

        Args:
            agent_id: The agent identifier.
            scenario: The scenario name.

        Returns:
            The loaded Snapshot.

        Raises:
            SnapshotNotFoundError: If no matching snapshot exists.
            ValueError: If agent_id or scenario contains unsafe characters.
        """
        self._validate_name(agent_id, "agent_id")
        self._validate_name(scenario, "scenario")

        logger.debug("Loading snapshot for %s/%s", agent_id, scenario)
        agent_dir = self.base_dir / agent_id
        if not agent_dir.exists():
            raise SnapshotNotFoundError(agent_id, scenario)

        # Find matching files
        matches = list(agent_dir.glob(f"{scenario}_*.json"))
        if not matches:
            raise SnapshotNotFoundError(agent_id, scenario)

        # Use the most recent file if multiple exist
        latest = max(matches, key=lambda p: p.stat().st_mtime)
        data = json.loads(latest.read_text(encoding="utf-8"))
        return Snapshot.from_dict(data)

    def load_all(self, agent_id: str) -> list[Snapshot]:
        """Load all snapshots for an agent."""
        agent_dir = self.base_dir / agent_id
        if not agent_dir.exists():
            return []

        snapshots: list[Snapshot] = []
        for filepath in sorted(agent_dir.glob("*.json")):
            data = json.loads(filepath.read_text(encoding="utf-8"))
            snapshots.append(Snapshot.from_dict(data))
        return snapshots

    def exists(self, agent_id: str, scenario: str) -> bool:
        """Check if a snapshot exists."""
        agent_dir = self.base_dir / agent_id
        if not agent_dir.exists():
            return False
        return bool(list(agent_dir.glob(f"{scenario}_*.json")))

    def list_agents(self) -> list[str]:
        """List all agent IDs with stored snapshots."""
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]

    def list_scenarios(self, agent_id: str) -> list[str]:
        """List all scenarios for an agent."""
        agent_dir = self.base_dir / agent_id
        if not agent_dir.exists():
            return []
        scenarios: set[str] = set()
        for filepath in agent_dir.glob("*.json"):
            # filename format: {scenario}_{hash}.json
            name = filepath.stem
            scenario = name.rsplit("_", 1)[0]
            scenarios.add(scenario)
        return sorted(scenarios)
