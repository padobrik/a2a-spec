"""agent-handshake: The open specification for agent-to-agent interactions."""

__version__ = "0.8.0"

from agent_handshake.adapters.a2a_adapter import A2AAdapter
from agent_handshake.adapters.base import AgentAdapter, AgentMetadata, AgentResponse
from agent_handshake.adapters.function_adapter import FunctionAdapter
from agent_handshake.adapters.http_adapter import HTTPAdapter
from agent_handshake.api import CheckResult, SnapshotResult, check, load_snapshots
from agent_handshake.config.loader import load_config
from agent_handshake.config.settings import HandshakeConfig
from agent_handshake.diff.engine import DiffEngine, DiffResult, DriftSeverity
from agent_handshake.exceptions import (
    AdapterError,
    ConfigError,
    HandshakeError,
    PolicyViolationError,
    SnapshotMismatchError,
    SnapshotNotFoundError,
    SpecValidationError,
)
from agent_handshake.snapshot.recorder import Recorder
from agent_handshake.snapshot.replay import ReplayEngine
from agent_handshake.snapshot.store import SnapshotStore
from agent_handshake.spec.loader import load_spec
from agent_handshake.spec.schema import PolicyRule, Spec, StructuralSpec
from agent_handshake.spec.validator import validate_output

__all__ = [
    # Core API
    "CheckResult",
    "SnapshotResult",
    "check",
    "load_snapshots",
    "__version__",
    # Spec
    "Spec",
    "StructuralSpec",
    "PolicyRule",
    "load_spec",
    "validate_output",
    # Snapshots
    "SnapshotStore",
    "Recorder",
    "ReplayEngine",
    # Diff
    "DiffEngine",
    "DiffResult",
    "DriftSeverity",
    # Adapters
    "A2AAdapter",
    "AgentAdapter",
    "AgentResponse",
    "AgentMetadata",
    "FunctionAdapter",
    "HTTPAdapter",
    # Config
    "HandshakeConfig",
    "load_config",
    # Exceptions
    "HandshakeError",
    "SpecValidationError",
    "SnapshotNotFoundError",
    "SnapshotMismatchError",
    "PolicyViolationError",
    "AdapterError",
    "ConfigError",
]
