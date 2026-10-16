"""Global configuration model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StorageConfig(BaseModel):
    """Configuration for snapshot storage."""

    model_config = ConfigDict(extra="forbid")

    backend: str = "local"
    path: str = "./handshake/snapshots"


class CIConfig(BaseModel):
    """Configuration for CI behavior."""

    model_config = ConfigDict(extra="forbid")

    replay_mode: str = "exact"


class HandshakeConfig(BaseModel):
    """Top-level project configuration."""

    model_config = ConfigDict(extra="forbid")

    project_name: str = "my-project"
    version: str = "1.0"
    specs_dir: str = "./handshake/specs"
    scenarios_dir: str = "./handshake/scenarios"
    adapters_dir: str = "./handshake/adapters"
    storage: StorageConfig = Field(default_factory=StorageConfig)
    ci: CIConfig = Field(default_factory=CIConfig)
