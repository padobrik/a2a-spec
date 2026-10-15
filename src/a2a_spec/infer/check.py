"""Check that an inferred spec still covers what the consumer code reads."""

from __future__ import annotations

from dataclasses import dataclass, field

from a2a_spec.infer.consumer import analyze_consumer, parse_source_ref
from a2a_spec.spec.schema import Spec


@dataclass(frozen=True)
class FreshnessResult:
    """Problems found when comparing a spec with its consumer's code.

    ``failures`` mean the spec no longer protects the consumer; ``warnings``
    mean the spec is stricter than the code needs, or the analysis is partial.
    """

    spec: Spec
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def check_inferred_spec(spec: Spec) -> FreshnessResult:
    """Compare a spec made by ``a2aspec infer`` with its consumer's current code.

    Raises:
        ValueError: If the spec has no ``inferred_from``.
        ConfigError: If the consumer source cannot be found or parsed.
    """
    if not spec.inferred_from:
        raise ValueError(f"Spec '{spec.name}' was not inferred from code")

    path, function = parse_source_ref(spec.inferred_from)
    reads = analyze_consumer(path, function)
    covered = set(spec.structural.properties) | set(spec.structural.required)
    required = set(spec.structural.required)

    failures: list[str] = []
    for name in reads.fields:
        lines = ", ".join(str(r.line) for r in reads.reads if r.name == name)
        strict = any(r.strict for r in reads.reads if r.name == name)
        if name not in covered:
            failures.append(
                f"{function} reads '{name}' (line {lines}), which the spec does not cover"
            )
        elif strict and name not in required:
            failures.append(
                f"{function} reads '{name}' with [] (line {lines}), but the spec makes it optional"
            )

    read = set(reads.fields)
    warnings = [
        f"the spec covers '{name}', which {function} no longer reads"
        for name in sorted(covered - read)
    ]
    warnings += reads.warnings
    return FreshnessResult(spec=spec, failures=failures, warnings=warnings)
