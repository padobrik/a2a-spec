"""Policy evaluation engine."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from a2a_spec.spec.schema import PolicyRule


@dataclass
class PolicyResult:
    """Result of a single policy check."""

    rule_name: str
    passed: bool
    detail: str = ""


class PolicyEngine:
    """Evaluates policy rules against agent outputs.

    Policies are hard rules that must always pass — unlike semantic
    checks which have thresholds, policies are binary pass/fail.
    """

    def __init__(self) -> None:
        self._custom_validators: dict[str, Any] = {}

    def register_validator(self, name: str, fn: Any) -> None:
        """Register a custom policy validator function.

        The function signature must be:
            def validator(output: dict, input_data: dict) -> tuple[bool, str]

        Args:
            name: Dotted name matching the spec's validator field.
            fn: The validator function.
        """
        self._custom_validators[name] = fn

    def evaluate(
        self,
        output: dict[str, Any],
        input_data: dict[str, Any],
        rules: list[PolicyRule],
    ) -> list[PolicyResult]:
        """Evaluate all policy rules against an output.

        Args:
            output: The agent output to check.
            input_data: The original input (for context).
            rules: List of policy rules from the spec.

        Returns:
            List of PolicyResult objects.
        """
        results: list[PolicyResult] = []

        for rule in rules:
            if rule.method == "regex":
                result = self._check_regex(output, rule)
            elif rule.method == "custom":
                result = self._check_custom(output, input_data, rule)
            else:
                result = PolicyResult(
                    rule_name=rule.rule,
                    passed=False,
                    detail=f"Unknown policy method: {rule.method}",
                )
            results.append(result)

        return results

    def _check_regex(self, output: dict[str, Any], rule: PolicyRule) -> PolicyResult:
        """Check that no output string matches forbidden patterns."""
        if not rule.patterns:
            return PolicyResult(rule_name=rule.rule, passed=True)

        compiled = [re.compile(p) for p in rule.patterns]

        for key, value in self._flatten_strings(output):
            for pattern in compiled:
                match = pattern.search(value)
                if match:
                    return PolicyResult(
                        rule_name=rule.rule,
                        passed=False,
                        detail=f"Pattern matched in field '{key}': '{match.group()}'",
                    )

        return PolicyResult(rule_name=rule.rule, passed=True)

    def _check_custom(
        self,
        output: dict[str, Any],
        input_data: dict[str, Any],
        rule: PolicyRule,
    ) -> PolicyResult:
        """Run a custom validator function."""
        if not rule.validator:
            return PolicyResult(
                rule_name=rule.rule,
                passed=False,
                detail="Custom rule missing 'validator' field",
            )

        fn = self._custom_validators.get(rule.validator)
        if fn is None:
            return PolicyResult(
                rule_name=rule.rule,
                passed=False,
                detail=f"Validator '{rule.validator}' not registered",
            )

        try:
            passed, detail = fn(output, input_data)
        except Exception as e:
            return PolicyResult(
                rule_name=rule.rule,
                passed=False,
                detail=f"Validator raised: {e}",
            )

        return PolicyResult(rule_name=rule.rule, passed=passed, detail=detail)

    @staticmethod
    def _flatten_strings(data: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
        """Recursively extract all string values from a dict."""
        strings: list[tuple[str, str]] = []
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, str):
                strings.append((full_key, value))
            elif isinstance(value, dict):
                strings.extend(PolicyEngine._flatten_strings(value, full_key))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, str):
                        strings.append((f"{full_key}[{i}]", item))
                    elif isinstance(item, dict):
                        strings.extend(PolicyEngine._flatten_strings(item, f"{full_key}[{i}]"))
        return strings
