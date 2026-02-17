"""GitHub Actions annotations for CI integration."""

from __future__ import annotations

from a2a_spec.diff.engine import DiffResult, DriftSeverity
from a2a_spec.spec.validator import ValidationResult


def format_github_annotation(
    file: str,
    line: int,
    level: str,
    message: str,
    title: str = "a2a-spec",
) -> str:
    """Format a single GitHub Actions annotation.

    Args:
        file: File path for the annotation.
        line: Line number.
        level: One of 'error', 'warning', 'notice'.
        message: The annotation message.
        title: Optional title prefix.

    Returns:
        GitHub annotation string.
    """
    return f"::{level} file={file},line={line},title={title}::{message}"


def generate_annotations(
    spec_name: str,
    validation: ValidationResult,
    diff_results: list[DiffResult] | None = None,
) -> list[str]:
    """Generate GitHub Actions annotations from validation and diff results.

    Args:
        spec_name: The spec that was validated.
        validation: Structural validation result.
        diff_results: Optional semantic diff results.

    Returns:
        List of GitHub annotation strings.
    """
    annotations: list[str] = []

    for error in validation.errors:
        annotations.append(
            format_github_annotation(
                file=f"a2a_spec/specs/{spec_name}.yaml",
                line=1,
                level="error",
                message=f"Spec validation failed: {error}",
            )
        )

    for warning in validation.warnings:
        annotations.append(
            format_github_annotation(
                file=f"a2a_spec/specs/{spec_name}.yaml",
                line=1,
                level="warning",
                message=f"Spec warning: {warning}",
            )
        )

    if diff_results:
        for dr in diff_results:
            level = (
                "error"
                if dr.severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL)
                else "warning"
            )
            annotations.append(
                format_github_annotation(
                    file=f"a2a_spec/specs/{spec_name}.yaml",
                    line=1,
                    level=level,
                    message=f"[{dr.severity.value}] {dr.field}: {dr.explanation}",
                )
            )

    return annotations


def print_annotations(annotations: list[str]) -> None:
    """Print annotations to stdout for GitHub Actions to pick up.

    Args:
        annotations: List of formatted annotation strings.
    """
    for annotation in annotations:
        # GitHub Actions reads annotations from stdout
        import sys

        sys.stdout.write(annotation + "\n")
