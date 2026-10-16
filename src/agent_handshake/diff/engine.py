"""Diff engine that rates structural changes between two outputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from agent_handshake.diff.structural import FieldDiff, structural_diff
from agent_handshake.output import AgentOutput

logger = logging.getLogger(__name__)

# The field name of a change to the whole output, such as a different text.
OUTPUT_FIELD = "(output)"


class DriftSeverity(StrEnum):
    """Severity levels for detected drift."""

    NONE = "none"
    INFO = "info"  # a change no consumer spec reads
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DiffResult:
    """Diff result for a single field."""

    field: str
    severity: DriftSeverity
    structural: FieldDiff | None = None
    explanation: str = ""


class DiffEngine:
    """Compares two agent outputs field by field.

    Usage:
        results = DiffEngine().diff(old_output, new_output)
        for r in results:
            print(f"{r.field}: {r.severity} — {r.explanation}")
    """

    def diff(self, old_output: AgentOutput, new_output: AgentOutput) -> list[DiffResult]:
        """One DiffResult per field that was added, removed or changed.

        Text output is compared as a whole, under the field ``OUTPUT_FIELD``.
        """
        if isinstance(old_output, dict) and isinstance(new_output, dict):
            field_diffs = structural_diff(old_output, new_output)
        else:
            field_diffs = _whole_output_diff(old_output, new_output)
        logger.info("Diff found %d structural difference(s)", len(field_diffs))
        return [
            DiffResult(
                field=fd.field,
                severity=self._structural_severity(fd),
                structural=fd,
                explanation=fd.detail,
            )
            for fd in field_diffs
        ]

    @staticmethod
    def _structural_severity(fd: FieldDiff) -> DriftSeverity:
        """Determine severity based on structural change type.

        A new field is LOW: consumers ignore fields they do not read. A
        removed field is HIGH because a consumer may depend on it.
        """
        if fd.change_type == "added":
            return DriftSeverity.LOW
        if fd.change_type == "removed":
            return DriftSeverity.HIGH
        if fd.change_type == "type_changed":
            return DriftSeverity.CRITICAL
        return DriftSeverity.MEDIUM


def _whole_output_diff(old: AgentOutput, new: AgentOutput) -> list[FieldDiff]:
    """The change when one side is text: it changed, or it changed between text and object."""
    if old == new:
        return []
    kinds = {True: "text", False: "an object"}
    old_text, new_text = isinstance(old, str), isinstance(new, str)
    if old_text != new_text:
        detail = f"The output changed from {kinds[old_text]} to {kinds[new_text]}"
        return [FieldDiff(OUTPUT_FIELD, "type_changed", old, new, detail)]
    return [FieldDiff(OUTPUT_FIELD, "changed", old, new, "The text output changed")]
