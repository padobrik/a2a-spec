"""Tests for console reporting."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from a2a_spec.reporting.console import print_summary, print_validation_result
from a2a_spec.spec.validator import ValidationResult


class TestConsoleReporting:
    def test_print_summary_all_passed(self) -> None:
        _console = Console(file=StringIO())  # noqa: F841
        # Just verify it doesn't crash with valid inputs
        print_summary(5, 5, 0)

    def test_print_summary_with_failures(self) -> None:
        print_summary(10, 7, 3)

    def test_print_summary_with_warnings(self) -> None:
        print_summary(10, 8, 1, warnings=1)

    def test_print_validation_passed(self) -> None:
        result = ValidationResult()
        print_validation_result("test-spec", "scenario1", result)

    def test_print_validation_failed(self) -> None:
        result = ValidationResult()
        result.add_error("Missing field 'category'")
        result.add_error("Invalid type for 'priority'")
        print_validation_result("test-spec", "scenario1", result)

    def test_print_validation_with_policy(self) -> None:
        from a2a_spec.policy.engine import PolicyResult

        result = ValidationResult()
        policies = [PolicyResult(rule_name="no_pii", passed=True)]
        print_validation_result("test-spec", "scenario1", result, policies)

    def test_print_validation_with_failed_policy(self) -> None:
        from a2a_spec.policy.engine import PolicyResult

        result = ValidationResult()
        policies = [PolicyResult(rule_name="no_pii", passed=False, detail="PII found")]
        print_validation_result("test-spec", "scenario1", result, policies)
