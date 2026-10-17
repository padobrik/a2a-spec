"""GitHub Actions annotations for CI integration."""

from __future__ import annotations


def format_github_annotation(
    file: str,
    line: int,
    level: str,
    message: str,
    title: str = "agent-handshake",
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
    return (
        f"::{level} file={_escape_property(file)},line={line},"
        f"title={_escape_property(title)}::{_escape_data(message)}"
    )


def _escape_data(value: str) -> str:
    """Escape a workflow command message (GitHub Actions toolkit rules)."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    """Escape a workflow command property value."""
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def print_annotations(annotations: list[str]) -> None:
    """Print annotations to stdout for GitHub Actions to pick up.

    Args:
        annotations: List of formatted annotation strings.
    """
    for annotation in annotations:
        # GitHub Actions reads annotations from stdout
        import sys

        sys.stdout.write(annotation + "\n")
