"""Tests for built-in policy validators."""

from __future__ import annotations

from a2a_spec.policy.builtin import no_pii_in_output, output_not_empty


class TestNoPII:
    def test_clean_output_passes(self) -> None:
        passed, detail = no_pii_in_output({"text": "Hello world"}, {})
        assert passed

    def test_credit_card_detected(self) -> None:
        passed, detail = no_pii_in_output({"text": "Card: 4111 1111 1111 1111"}, {})
        assert not passed
        assert "credit_card" in detail

    def test_ssn_detected(self) -> None:
        passed, detail = no_pii_in_output({"text": "SSN: 123-45-6789"}, {})
        assert not passed
        assert "ssn" in detail

    def test_email_detected(self) -> None:
        passed, detail = no_pii_in_output({"text": "Contact: user@example.com"}, {})
        assert not passed
        assert "email" in detail

    def test_nested_pii_detected(self) -> None:
        passed, detail = no_pii_in_output({"nested": {"deep": "Call 555.123.4567"}}, {})
        assert not passed


class TestOutputNotEmpty:
    def test_valid_output_passes(self) -> None:
        passed, detail = output_not_empty({"text": "This is a proper response"}, {})
        assert passed

    def test_empty_dict_fails(self) -> None:
        passed, detail = output_not_empty({}, {})
        assert not passed

    def test_trivially_short_fails(self) -> None:
        passed, detail = output_not_empty({"x": "hi"}, {})
        assert not passed
        assert "too short" in detail

    def test_numeric_only_passes(self) -> None:
        passed, detail = output_not_empty({"score": 0.95, "text": "Valid response here"}, {})
        assert passed
