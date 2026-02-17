"""a2a-spec: The open specification for agent-to-agent interactions."""

__version__ = "0.1.0"

from a2a_spec.adapters.base import AgentAdapter, AgentMetadata, AgentResponse
from a2a_spec.adapters.function_adapter import FunctionAdapter
from a2a_spec.adapters.http_adapter import HTTPAdapter
from a2a_spec.config.loader import load_config
from a2a_spec.config.settings import A2ASpecConfig
from a2a_spec.diff.engine import DiffEngine, DiffResult, DriftSeverity
from a2a_spec.exceptions import (
    A2ASpecError,
    AdapterError,
    ConfigError,
    PipelineExecutionError,
    PolicyViolationError,
    SemanticDriftError,
    SnapshotMismatchError,
    SnapshotNotFoundError,
    SpecValidationError,
)
from a2a_spec.pipeline.executor import PipelineExecutor
from a2a_spec.pipeline.trace import PipelineTrace
from a2a_spec.snapshot.recorder import Recorder
from a2a_spec.snapshot.replay import ReplayEngine
from a2a_spec.snapshot.store import SnapshotStore
from a2a_spec.spec.loader import load_spec
from a2a_spec.spec.schema import PolicyRule, SemanticRule, Spec, StructuralSpec
from a2a_spec.spec.validator import validate_output

__all__ = [
    "__version__",
    # Spec
    "Spec",
    "StructuralSpec",
    "SemanticRule",
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
    # Pipeline
    "PipelineExecutor",
    "PipelineTrace",
    # Adapters
    "AgentAdapter",
    "AgentResponse",
    "AgentMetadata",
    "FunctionAdapter",
    "HTTPAdapter",
    # Config
    "A2ASpecConfig",
    "load_config",
    # Exceptions
    "A2ASpecError",
    "SpecValidationError",
    "SnapshotNotFoundError",
    "SnapshotMismatchError",
    "SemanticDriftError",
    "PolicyViolationError",
    "PipelineExecutionError",
    "AdapterError",
    "ConfigError",
]
