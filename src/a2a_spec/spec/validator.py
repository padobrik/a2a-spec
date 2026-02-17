"""Validate agent outputs against spec schemas."""

from __future__ import annotations

from typing import Any

import jsonschema

from a2a_spec.spec.schema import Spec, StructuralSpec


class ValidationResult:
    """Result of validating an output against a spec."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def passed(self) -> bool:
        """Whether the validation passed (no errors)."""
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        """Add a validation error."""
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        """Add a validation warning."""
        self.warnings.append(msg)

    def __repr__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"ValidationResult({status}, errors={len(self.errors)}, warnings={len(self.warnings)})"
        )


def validate_structural(output: dict[str, Any], structural: StructuralSpec) -> ValidationResult:
    """Validate output against JSON Schema structural spec.

    Args:
        output: The agent output to validate.
        structural: The structural specification.

    Returns:
        ValidationResult with any errors found.
    """
    result = ValidationResult()

    # Build JSON Schema from StructuralSpec
    schema: dict[str, Any] = {
        "type": structural.type,
    }
    if structural.required:
        schema["required"] = structural.required
    if structural.properties:
        schema["properties"] = structural.properties

    # Validate using jsonschema
    validator = jsonschema.Draft7Validator(schema)
    for error in validator.iter_errors(output):
        # Build human-readable error path
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "<root>"
        result.add_error(f"[{path}] {error.message}")

    return result


def validate_output(output: dict[str, Any], spec: Spec) -> ValidationResult:
    """Validate an agent output against a full spec.

    This runs structural validation. Semantic and policy validation
    are handled by their respective engines.

    Args:
        output: The agent output to validate.
        spec: The spec to validate against.

    Returns:
        ValidationResult with all errors and warnings.
    """
    return validate_structural(output, spec.structural)
