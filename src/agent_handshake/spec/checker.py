"""Run every validation layer of a spec against one snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from a2a_spec.policy.engine import PolicyEngine, PolicyResult
from a2a_spec.semantic.engine import SemanticEngine, SemanticResult
from a2a_spec.spec.schema import Spec
from a2a_spec.spec.validator import ValidationResult, validate_output


@dataclass(frozen=True)
class SpecCheck:
    """Outcome of checking one output against one spec.

    ``semantic`` is None when semantic rules were not evaluated.
    """

    spec: Spec
    structural: ValidationResult
    policy: list[PolicyResult]
    semantic: list[SemanticResult] | None
    expectations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when every evaluated layer passed."""
        return (
            self.structural.passed
            and all(p.passed for p in self.policy)
            and all(r.passed for r in self.semantic or [])
            and not self.expectations
        )

    @property
    def semantic_skipped(self) -> bool:
        """True when the spec has semantic rules that were not evaluated."""
        return self.semantic is None and bool(self.spec.semantic)

    def failures(self) -> list[str]:
        """Human-readable failure lines, one per problem."""
        lines = [f"structural: {e}" for e in self.structural.errors]
        lines += [f"policy {p.rule_name}: {p.detail}" for p in self.policy if not p.passed]
        lines += [
            f"semantic {r.rule_name}: {r.detail}" for r in self.semantic or [] if not r.passed
        ]
        lines += [f"expectation: {e}" for e in self.expectations]
        return lines


class SpecChecker:
    """Checks outputs against specs with shared, reusable engines.

    Pass ``semantic_engine=None`` to skip semantic rules.

    Raises (from ``check``):
        ImportError: If semantic rules need the missing ``semantic`` extra.
    """

    def __init__(
        self,
        policy_engine: PolicyEngine | None = None,
        semantic_engine: SemanticEngine | None = None,
    ) -> None:
        self.policy_engine = policy_engine or PolicyEngine()
        self.semantic_engine = semantic_engine

    def check(
        self,
        spec: Spec,
        output: dict[str, Any],
        input_data: dict[str, Any],
        expected: dict[str, Any] | None = None,
    ) -> SpecCheck:
        """Run structural, policy, (if enabled) semantic and expectation checks.

        ``expected`` maps output fields to the exact values a scenario expects.
        """
        semantic = None
        if self.semantic_engine is not None:
            semantic = self.semantic_engine.evaluate(output, input_data, spec.semantic)
        return SpecCheck(
            spec=spec,
            structural=validate_output(output, spec),
            policy=self.policy_engine.evaluate(output, input_data, spec.policy),
            semantic=semantic,
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
