"""Tests for spec structural validation."""

from __future__ import annotations

import pytest

from a2a_spec.spec.schema import Spec, StructuralSpec
from a2a_spec.spec.validator import ValidationResult, validate_output


@pytest.fixture
def billing_spec() -> Spec:
    return Spec(
        name="triage-to-billing",
        version="1.0",
        producer="triage-agent",
        consumer="billing-agent",
        structural=StructuralSpec(
            type="object",
            required=["category", "priority", "summary"],
            properties={
                "category": {"type": "string", "enum": ["billing", "shipping", "general"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "summary": {"type": "string", "minLength": 10},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
        ),
    )


class TestValidateStructural:
    def test_valid_output_passes(self, billing_spec: Spec) -> None:
        output = {
            "category": "billing",
            "priority": "high",
            "summary": "Customer was charged twice for order",
            "confidence": 0.95,
        }
        result = validate_output(output, billing_spec)
        assert result.passed
        assert len(result.errors) == 0

    def test_missing_required_field_fails(self, billing_spec: Spec) -> None:
        output = {"category": "billing"}
        result = validate_output(output, billing_spec)
        assert not result.passed
        assert any("priority" in e for e in result.errors)
        assert any("summary" in e for e in result.errors)

    def test_invalid_enum_value_fails(self, billing_spec: Spec) -> None:
        output = {
            "category": "refund",
            "priority": "high",
            "summary": "Customer wants a refund for their order",
        }
        result = validate_output(output, billing_spec)
        assert not result.passed
        assert any("refund" in e for e in result.errors)

    def test_string_too_short_fails(self, billing_spec: Spec) -> None:
        output = {
            "category": "billing",
            "priority": "high",
            "summary": "short",
        }
        result = validate_output(output, billing_spec)
        assert not result.passed

    def test_number_out_of_range_fails(self, billing_spec: Spec) -> None:
        output = {
            "category": "billing",
            "priority": "high",
            "summary": "Customer was charged twice for order",
            "confidence": 1.5,
        }
        result = validate_output(output, billing_spec)
        assert not result.passed

    def test_extra_fields_allowed(self, billing_spec: Spec) -> None:
        output = {
            "category": "billing",
            "priority": "high",
            "summary": "Customer was charged twice for order",
            "extra_field": "this is fine",
        }
        result = validate_output(output, billing_spec)
        assert result.passed

    def test_empty_output_fails(self, billing_spec: Spec) -> None:
        result = validate_output({}, billing_spec)
        assert not result.passed
        assert len(result.errors) >= 3

    def test_validation_result_repr(self) -> None:
        result = ValidationResult()
        assert "PASSED" in repr(result)
        result.add_error("some error")
        assert "FAILED" in repr(result)
