"""Generate human-readable diff reports."""

from __future__ import annotations

from a2a_spec.diff.engine import DiffResult, DriftSeverity

SEVERITY_ICONS: dict[DriftSeverity, str] = {
    DriftSeverity.NONE: "✓",
    DriftSeverity.LOW: "~",
    DriftSeverity.MEDIUM: "⚠",
    DriftSeverity.HIGH: "✗",
    DriftSeverity.CRITICAL: "🚨",
}


def format_diff_results(
    agent_id: str,
    scenario: str,
    results: list[DiffResult],
) -> str:
    """Format diff results as a readable string.

    Args:
        agent_id: The agent that produced the outputs.
        scenario: The test scenario name.
        results: List of diff results.

    Returns:
        Formatted multi-line string.
    """
    if not results:
        return f"  {agent_id} / {scenario}: ✓ No differences"

    lines = [f"  {agent_id} / {scenario}:"]
    for r in results:
        icon = SEVERITY_ICONS.get(r.severity, "?")
        lines.append(f"    {icon} {r.field}: {r.explanation}")

        if r.structural and r.structural.old_value is not None:
            old_str = _truncate(str(r.structural.old_value), 80)
            lines.append(f"      OLD: {old_str}")
        if r.structural and r.structural.new_value is not None:
            new_str = _truncate(str(r.structural.new_value), 80)
            lines.append(f"      NEW: {new_str}")

    return "\n".join(lines)


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to a maximum length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
