"""Local file-based snapshot storage."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_handshake.exceptions import SnapshotFormatError, SnapshotNotFoundError
from agent_handshake.output import AgentOutput
from agent_handshake.snapshot.fingerprint import Fingerprint

logger = logging.getLogger(__name__)

# Version of the snapshot file format. Files written before the field existed
# are read as version 1.
SCHEMA_VERSION = 1

# Fields that decide whether a snapshot file on disk is already up to date.
_CONTENT_FIELDS = ("schema_version", "agent_id", "scenario", "input", "output")


class Snapshot:
    """A recorded agent interaction."""

    def __init__(
        self,
        fingerprint: Fingerprint,
        scenario: str,
        input_data: dict[str, Any],
        output_data: AgentOutput,
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
            "schema_version": SCHEMA_VERSION,
            "fingerprint": self.fingerprint.key,
            "agent_id": self.fingerprint.agent_id,
            "scenario": self.scenario,
            "timestamp": self.timestamp,
            "input": self.input_data,
            "output": self.output_data,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Any, source: str = "data") -> Snapshot:
        """Deserialize a snapshot from a dict.

        ``source`` names the file in error messages.

        Raises:
            SnapshotFormatError: If the data is not a snapshot of a supported version.
        """
        if not isinstance(data, dict):
            raise SnapshotFormatError(source, "must be a JSON object")
        version = data.get("schema_version")
        if "schema_version" not in data:
            logger.warning(
                "Snapshot %s has no schema_version; read as version 1. "
                "Record it again with 'handshake record' to add it.",
                source,
            )
        elif not isinstance(version, int) or isinstance(version, bool):
            raise SnapshotFormatError(source, "has a schema_version that is not an integer")
        elif version < 1:
            raise SnapshotFormatError(source, f"has schema_version {version}; versions start at 1")
        elif version > SCHEMA_VERSION:
            raise SnapshotFormatError(
                source,
                f"has schema_version {version}, but this agent-handshake reads "
                f"version {SCHEMA_VERSION}",
                fix="Upgrade agent-handshake.",
            )
        kinds: tuple[tuple[str, type | tuple[type, ...], str], ...] = (
            ("agent_id", str, "a string"),
            ("scenario", str, "a string"),
            ("input", dict, "an object"),
            ("output", (dict, str), "an object or a string"),
        )
        for key, kind, name in kinds:
            if key not in data:
                raise SnapshotFormatError(source, f"has no '{key}' field")
            if not isinstance(data[key], kind):
                raise SnapshotFormatError(source, f"has a '{key}' field that is not {name}")
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
            metadata=data.get("metadata") or {},
        )


def parse_snapshot(text: str, source: str) -> Snapshot:
    """Parse snapshot JSON; ``source`` names the file in error messages.

    Raises:
        SnapshotFormatError: If the text is not valid snapshot JSON.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise SnapshotFormatError(
            source, f"is not valid JSON ({e.msg} at line {e.lineno}, column {e.colno})"
        ) from e
    return Snapshot.from_dict(data, source)


def read_snapshot(path: Path) -> Snapshot:
    """Read a snapshot file.

    Raises:
        SnapshotFormatError: If the file cannot be read or is not a valid snapshot.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise SnapshotFormatError(str(path), f"cannot be read ({e})") from e
    return parse_snapshot(text, str(path))


def _canonical(value: Any) -> str:
    """JSON text of a value with sorted keys; keeps the difference between JSON types."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


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

        data = snapshot.to_dict()
        if self._unchanged(filepath, data):
            logger.info("Snapshot %s is unchanged; the file is kept as it is", filepath)
            return filepath
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.debug("Saved snapshot to %s", filepath)
        logger.info("Saved snapshot for %s/%s", snapshot.fingerprint.agent_id, snapshot.scenario)
        return filepath

    @staticmethod
    def _unchanged(filepath: Path, data: dict[str, Any]) -> bool:
        """True when the file already holds the same input, output and format version.

        Then a new record keeps the file, so git shows no change.
        """
        if not filepath.exists():
            return False
        try:
            old = json.loads(filepath.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        if not isinstance(old, dict):
            return False
        # Compare as JSON so that 1, 1.0 and true count as different values.
        return all(_canonical(old.get(k)) == _canonical(data[k]) for k in _CONTENT_FIELDS)

    def load(self, agent_id: str, scenario: str) -> Snapshot:
        """Load the latest snapshot for an agent + scenario.

        Args:
            agent_id: The agent identifier.
            scenario: The scenario name.

        Returns:
            The loaded Snapshot.

        Raises:
            SnapshotNotFoundError: If no matching snapshot exists.
            SnapshotFormatError: If the file is not a valid snapshot.
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
        return read_snapshot(latest)

    def load_all(self, agent_id: str) -> list[Snapshot]:
        """Load all snapshots for an agent."""
        agent_dir = self.base_dir / agent_id
        if not agent_dir.exists():
            return []

        snapshots: list[Snapshot] = []
        for filepath in sorted(agent_dir.glob("*.json")):
            snapshots.append(read_snapshot(filepath))
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
