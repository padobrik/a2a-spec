"""Rate diff results by what the producer's consumers read.

Without a spec a removed field is HIGH, because some consumer may read it.
With specs we know: a removed or retyped field that a spec names breaks that
consumer (HIGH, shown as FAIL), and a change to a field no spec names is INFO.
"""

from __future__ import annotations

from dataclasses import replace

from agent_handshake.diff.engine import DiffResult, DriftSeverity
from agent_handshake.spec.fields import field_paths, spec_schema
from agent_handshake.spec.schema import Spec

_BREAKING = ("removed", "type_changed")


def rate_for_consumers(results: list[DiffResult], specs: list[Spec]) -> list[DiffResult]:
    """Re-rate ``results`` for one producer against the specs of its consumers.

    ``specs`` are the specs whose producer is the agent the results belong to.
    With no specs the results are returned unchanged.
    """
    if not specs:
        return results
    named = [(spec, {".".join(p) for p in field_paths(spec_schema(spec))}) for spec in specs]
    rated: list[DiffResult] = []
    for result in results:
        readers = [spec for spec, paths in named if _names(paths, result.field)]
        change = result.structural.change_type if result.structural else ""
        if not readers:
            rated.append(
                replace(
                    result,
                    severity=DriftSeverity.INFO,
                    explanation=f"{result.explanation}; no consumer spec reads it",
                )
            )
        elif change in _BREAKING:
            where = "; ".join(_reader(spec, result.field) for spec in readers)
            rated.append(
                replace(
                    result,
                    severity=DriftSeverity.HIGH,
                    explanation=f"{result.explanation}; {where}",
                )
            )
        else:
            rated.append(result)
    return rated


def _names(paths: set[str], field: str) -> bool:
    """True when the spec names ``field`` or something below it."""
    return field in paths or any(p.startswith(f"{field}.") for p in paths)


def _reader(spec: Spec, field: str) -> str:
    """Who reads ``field`` and where, as far as the spec says."""
    lines = sorted(
        {
            line
            for path, found in spec.read_at.items()
            if path == field or path.startswith(f"{field}.")
            for line in found
        }
    )
    if spec.inferred_from and lines:
        source = spec.inferred_from.rsplit(":", 1)[0]
        places = ", ".join(f"{source}:{line}" for line in lines)
        return f"{spec.consumer} reads it at {places}"
    return f"spec '{spec.name}' for {spec.consumer} names it"
