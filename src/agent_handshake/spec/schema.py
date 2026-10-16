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
    # Lines where the consumer reads each field, by dotted path, for example
    # {"customer.tier": [3]}. Set by `handshake infer`; `handshake diff` uses it
    # to say where a removed field is read.
    read_at: dict[str, list[int]] = Field(default_factory=dict)
    # True when the consumer also reads keys `handshake infer` cannot name, for
    # example data[key]. Set by `handshake infer`; `handshake diff` then keeps
    # the rating of a changed field the spec does not name.
    reads_unknown_keys: bool = False
    # Fields the consumer reads that the producer leaves out on purpose, as
    # dotted paths. Set by `handshake infer --allow-missing`; they stay optional,
    # and `handshake infer --check` accepts a [] read of them.
    allow_missing: list[str] = Field(default_factory=list)

    structural: StructuralSpec
    policy: list[PolicyRule] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
