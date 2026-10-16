"""Diff engine that rates structural changes between two outputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agent_handshake.diff.structural import FieldDiff, structural_diff

logger = logging.getLogger(__name__)


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

    def diff(self, old_output: dict[str, Any], new_output: dict[str, Any]) -> list[DiffResult]:
        """One DiffResult per field that was added, removed or changed."""
        field_diffs = structural_diff(old_output, new_output)
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
