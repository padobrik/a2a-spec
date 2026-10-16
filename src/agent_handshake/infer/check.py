"""Check that an inferred spec still covers what the consumer code reads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_handshake.infer.consumer import analyze_consumer, parse_source_ref
from agent_handshake.spec.schema import Spec


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
    """Compare a spec made by ``handshake infer`` with its consumer's current code.

    Raises:
        ValueError: If the spec has no ``inferred_from``.
        ConfigError: If the consumer source cannot be found or parsed.
    """
    if not spec.inferred_from:
        raise ValueError(f"Spec '{spec.name}' was not inferred from code")

    path, function = parse_source_ref(spec.inferred_from)
    reads = analyze_consumer(path, function)
    root = {"required": spec.structural.required, "properties": spec.structural.properties}

    failures: list[str] = []
    reported: set[tuple[str, ...]] = set()
    for read in reads.reads:
        schema: Any = root
        for depth, key in enumerate(read.path):
            path_ = read.path[: depth + 1]
            name = ".".join(path_)
            below = [r for r in reads.reads if r.path[: depth + 1] == path_]
            lines = ", ".join(str(n) for n in sorted({r.line for r in below}))
            required = _list(schema, "required")
            properties = _dict(schema, "properties")
            if key not in properties and key not in required:
                problem = f"{function} reads '{name}' (line {lines}), which the spec does not cover"
            elif any(r.strict[depth] for r in below) and key not in required:
                problem = (
                    f"{function} reads '{name}' with [] (line {lines}), "
                    "but the spec makes it optional"
                )
            else:
                schema = properties.get(key, {})
                continue
            if path_ not in reported:
                reported.add(path_)
                failures.append(problem)
            break

    read_paths = {r.path[:n] for r in reads.reads for n in range(1, len(r.path) + 1)}
    warnings = [
        f"the spec covers '{'.'.join(p)}', which {function} no longer reads"
        for p in _covered(root, ())
        if p not in read_paths
    ]
    warnings += reads.warnings
    return FreshnessResult(spec=spec, failures=failures, warnings=warnings)


def _covered(schema: Any, parent: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Every key path the spec names, parents before children."""
    paths: list[tuple[str, ...]] = []
    properties = _dict(schema, "properties")
    for key in dict.fromkeys([*_list(schema, "required"), *properties]):
        path = (*parent, key)
        paths.append(path)
        paths += _covered(properties.get(key), path)
    return paths


def _list(schema: Any, key: str) -> list[Any]:
    value = schema.get(key) if isinstance(schema, dict) else None
    return value if isinstance(value, list) else []


def _dict(schema: Any, key: str) -> dict[str, Any]:
    value = schema.get(key) if isinstance(schema, dict) else None
    return value if isinstance(value, dict) else {}
