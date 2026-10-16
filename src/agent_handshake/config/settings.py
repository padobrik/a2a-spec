"""Global configuration model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SemanticConfig(BaseModel):
    """Configuration for semantic features."""

    provider: str = "sentence-transformers"
    model: str = "all-MiniLM-L6-v2"
    enabled: bool = True


class StorageConfig(BaseModel):
    """Configuration for snapshot storage."""

    backend: str = "local"
    path: str = "./handshake/snapshots"


class CIConfig(BaseModel):
    """Configuration for CI behavior."""

    fail_on_semantic_drift: bool = True
    drift_threshold: float = 0.15
    replay_mode: str = "exact"


class HandshakeConfig(BaseModel):
    """Top-level project configuration."""

    project_name: str = "my-project"
    version: str = "1.0"
    specs_dir: str = "./handshake/specs"
    scenarios_dir: str = "./handshake/scenarios"
    adapters_dir: str = "./handshake/adapters"
    semantic: SemanticConfig = Field(default_factory=SemanticConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    ci: CIConfig = Field(default_factory=CIConfig)


# Name before the rename to agent-handshake.
A2ASpecConfig = HandshakeConfig
