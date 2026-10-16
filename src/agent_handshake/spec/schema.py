"""Pydantic models representing agent-handshake YAML files."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PolicyMethod(StrEnum):
    """Supported policy check methods."""

    REGEX = "regex"
    CUSTOM = "custom"


class PolicyRule(BaseModel):
    """A hard policy enforcement rule."""

    rule: str
    description: str = ""
    method: PolicyMethod
    patterns: list[str] | None = None
    validator: str | None = None  # dotted path to custom validator function


class StructuralSpec(BaseModel):
    """JSON Schema-based structural specification."""

    type: str = "object"
    required: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class Spec(BaseModel):
    """Top-level spec model — represents one YAML spec file."""

    name: str
    version: str
    producer: str
    consumer: str
    description: str = ""
    # Consumer function the spec was inferred from, as path/to/file.py:function.
    # Set by `handshake infer`; `handshake infer --check` compares the spec with it.
    inferred_from: str | None = None

    structural: StructuralSpec
    policy: list[PolicyRule] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
