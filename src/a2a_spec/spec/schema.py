"""Pydantic models representing a2a-spec YAML files."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SemanticMethod(StrEnum):
    """Supported semantic validation methods."""

    ENTAILMENT = "entailment"
    EMBEDDING_SIMILARITY = "embedding_similarity"
    LANGUAGE_DETECTION = "language_detection"


class StatisticalMethod(StrEnum):
    """Supported statistical drift methods."""

    CHI_SQUARED = "chi_squared"
    KS_TEST = "ks_test"


class PolicyMethod(StrEnum):
    """Supported policy check methods."""

    REGEX = "regex"
    CUSTOM = "custom"


class SemanticRule(BaseModel):
    """A single semantic validation rule."""

    rule: str
    description: str = ""
    method: SemanticMethod
    threshold: float = 0.8
    source_field: str | None = None
    target_field: str | None = None


class StatisticalRule(BaseModel):
    """A statistical drift detection rule."""

    rule: str
    method: StatisticalMethod
    baseline: str | None = None
    max_drift: float = 0.15
    p_value_threshold: float = 0.05


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

    structural: StructuralSpec
    semantic: list[SemanticRule] = Field(default_factory=list)
    statistical: list[StatisticalRule] = Field(default_factory=list)
    policy: list[PolicyRule] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
