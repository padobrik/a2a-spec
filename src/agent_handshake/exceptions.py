"""All custom exceptions for agent-handshake."""

from __future__ import annotations


class HandshakeError(Exception):
    """Base exception for all agent-handshake errors."""


class SpecValidationError(HandshakeError):
    """Raised when an agent output fails spec validation."""

    def __init__(self, spec_name: str, errors: list[str]) -> None:
        self.spec_name = spec_name
        self.errors = errors
        msg = f"Spec '{spec_name}' validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(msg)


class SnapshotNotFoundError(HandshakeError):
    """Raised when a required snapshot does not exist."""

    def __init__(self, agent_id: str, scenario: str) -> None:
        self.agent_id = agent_id
        self.scenario = scenario
        super().__init__(
            f"No snapshot found for agent '{agent_id}', scenario '{scenario}'. "
            f"Run 'handshake record' first."
        )


class SnapshotMismatchError(HandshakeError):
    """Raised when a snapshot fingerprint does not match current config."""

    def __init__(self, agent_id: str, expected_hash: str, actual_hash: str) -> None:
        self.agent_id = agent_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(
            f"Snapshot fingerprint mismatch for '{agent_id}'. "
            f"Expected: {expected_hash}, Got: {actual_hash}. "
            f"Prompt or config may have changed. Run 'handshake record' to update."
        )


class SemanticDriftError(HandshakeError):
    """Raised when semantic drift exceeds threshold."""

    def __init__(self, field: str, similarity: float, threshold: float) -> None:
        self.field = field
        self.similarity = similarity
        self.threshold = threshold
        super().__init__(
            f"Semantic drift on field '{field}': "
            f"similarity={similarity:.3f}, threshold={threshold:.3f}"
        )


class PolicyViolationError(HandshakeError):
    """Raised when a policy rule is violated."""

    def __init__(self, rule_name: str, detail: str) -> None:
        self.rule_name = rule_name
        self.detail = detail
        super().__init__(f"Policy violation [{rule_name}]: {detail}")


class PipelineExecutionError(HandshakeError):
    """Raised when a pipeline execution fails."""

    def __init__(self, agent_id: str, cause: Exception) -> None:
        self.agent_id = agent_id
        self.cause = cause
        super().__init__(f"Pipeline failed at agent '{agent_id}': {cause}")


class AdapterError(HandshakeError):
    """Raised when an agent adapter fails."""

    def __init__(self, agent_id: str, detail: str) -> None:
        self.agent_id = agent_id
        self.detail = detail
        super().__init__(f"Adapter error for '{agent_id}': {detail}")


class ConfigError(HandshakeError):
    """Raised when configuration is invalid or missing."""
