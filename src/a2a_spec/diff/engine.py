"""Unified diff engine combining structural and semantic comparison."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from a2a_spec.diff.semantic import SemanticComparison, compute_similarity
from a2a_spec.diff.structural import FieldDiff, structural_diff

logger = logging.getLogger(__name__)


class DriftSeverity(StrEnum):
    """Severity levels for detected drift."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DiffResult:
    """Combined diff result for a single field.

    Note: DiffResult is intentionally mutable because severity and
    explanation are refined after semantic comparison in DiffEngine.diff().
    """

    field: str
    severity: DriftSeverity
    structural: FieldDiff | None = None
    semantic: SemanticComparison | None = None
    explanation: str = ""


class DiffEngine:
    """Compares two agent outputs structurally and semantically.

    Usage:
        engine = DiffEngine(semantic_model=model)
        results = engine.diff(old_output, new_output)
        for r in results:
            print(f"{r.field}: {r.severity} — {r.explanation}")
    """

    def __init__(self, semantic_model: object | None = None) -> None:
        self._model = semantic_model

    def diff(
        self,
        old_output: dict[str, Any],
        new_output: dict[str, Any],
        semantic_threshold: float = 0.85,
    ) -> list[DiffResult]:
        """Compute full diff between two outputs.

        Args:
            old_output: Baseline output.
            new_output: Current output.
            semantic_threshold: Minimum similarity for string fields.

        Returns:
            List of DiffResult objects, one per differing field.
        """
        results: list[DiffResult] = []

        # Step 1: Structural diff
        field_diffs = structural_diff(old_output, new_output)
        logger.info("Diff found %d structural difference(s)", len(field_diffs))

        for fd in field_diffs:
            result = DiffResult(
                field=fd.field,
                severity=self._structural_severity(fd),
                structural=fd,
                explanation=fd.detail,
            )

            # Step 2: Semantic comparison for changed string fields
            if (
                fd.change_type == "changed"
                and isinstance(fd.old_value, str)
                and isinstance(fd.new_value, str)
            ):
                sem = compute_similarity(fd.old_value, fd.new_value, self._model)
                result.semantic = sem
                logger.debug(
                    "Field '%s': similarity=%.3f, threshold=%.3f",
                    fd.field,
                    sem.similarity,
                    semantic_threshold,
                )

                if sem.above_threshold(semantic_threshold):
                    result.severity = DriftSeverity.LOW
                    result.explanation = (
                        f"Value changed but semantically similar (similarity: {sem.similarity:.3f})"
                    )
                else:
                    result.severity = DriftSeverity.HIGH
                    result.explanation = (
                        f"Semantic drift detected "
                        f"(similarity: {sem.similarity:.3f}, "
                        f"threshold: {semantic_threshold:.3f})"
                    )

            results.append(result)

        return results

    @staticmethod
    def _structural_severity(fd: FieldDiff) -> DriftSeverity:
        """Determine severity based on structural change type."""
        if fd.change_type in ("added", "removed"):
            return DriftSeverity.HIGH
        if fd.change_type == "type_changed":
            return DriftSeverity.CRITICAL
        return DriftSeverity.MEDIUM
