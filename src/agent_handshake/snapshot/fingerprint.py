"""Content-addressable fingerprinting for snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Fingerprint:
    """Unique identifier for a snapshot based on input + agent config.

    The fingerprint is a SHA256 hash of the agent_id, input data,
    and prompt version. If any of these change, the fingerprint changes,
    signaling that old snapshots may no longer be valid.
    """

    agent_id: str
    input_hash: str
    prompt_hash: str | None = None

    @property
    def key(self) -> str:
        """Short hash key for file naming and lookup."""
        content = json.dumps(
            {
                "agent_id": self.agent_id,
                "input_hash": self.input_hash,
                "prompt_hash": self.prompt_hash or "",
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    @classmethod
    def create(
        cls,
        agent_id: str,
        input_data: dict[str, Any],
        prompt_hash: str | None = None,
    ) -> Fingerprint:
        """Create a fingerprint from raw input data.

        Args:
            agent_id: The agent identifier.
            input_data: The input dict sent to the agent.
            prompt_hash: Optional hash of the agent's prompt template.

        Returns:
            A Fingerprint instance.
        """
        input_json = json.dumps(input_data, sort_keys=True, ensure_ascii=False)
        input_hash = hashlib.sha256(input_json.encode()).hexdigest()
        return cls(agent_id=agent_id, input_hash=input_hash, prompt_hash=prompt_hash)
