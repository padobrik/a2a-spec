"""Global configuration model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HandshakeConfig(BaseModel):
    """Top-level project configuration."""

    model_config = ConfigDict(extra="forbid")

    project_name: str = "my-project"
    version: str = "1.0"
