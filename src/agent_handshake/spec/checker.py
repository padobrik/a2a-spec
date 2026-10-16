"""Run every validation layer of a spec against one snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_handshake.policy.engine import PolicyEngine, PolicyResult
from agent_handshake.spec.schema import Spec
from agent_handshake.spec.validator import ValidationResult, validate_output


@dataclass(frozen=True)
class SpecCheck:
    """Outcome of checking one output against one spec."""

    spec: Spec
    structural: ValidationResult
    policy: list[PolicyResult]
    expectations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when every evaluated layer passed."""
        return (
            self.structural.passed and all(p.passed for p in self.policy) and not self.expectations
        )

    def failures(self) -> list[str]:
        """Human-readable failure lines, one per problem."""
        lines = [f"structural: {e}" for e in self.structural.errors]
        lines += [f"policy {p.rule_name}: {p.detail}" for p in self.policy if not p.passed]
        lines += [f"expectation: {e}" for e in self.expectations]
        return lines


class SpecChecker:
    """Checks outputs against specs with a shared, reusable policy engine."""

    def __init__(self, policy_engine: PolicyEngine | None = None) -> None:
        self.policy_engine = policy_engine or PolicyEngine()

    def check(
        self,
        spec: Spec,
        output: dict[str, Any],
        input_data: dict[str, Any],
        expected: dict[str, Any] | None = None,
    ) -> SpecCheck:
        """Run structural, policy and expectation checks.

        ``expected`` maps output fields to the exact values a scenario expects.
        """
        return SpecCheck(
            spec=spec,
            structural=validate_output(output, spec),
            policy=self.policy_engine.evaluate(output, input_data, spec.policy),
            expectations=check_expectations(output, expected or {}),
        )


def check_expectations(output: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """Compare output fields with the exact values a scenario expects."""
    problems: list[str] = []
    for key, value in expected.items():
        if key not in output:
            problems.append(f"expected '{key}' = {value!r}, but the field is missing")
        elif output[key] != value:
            problems.append(f"expected '{key}' = {value!r}, got {output[key]!r}")
    return problems
