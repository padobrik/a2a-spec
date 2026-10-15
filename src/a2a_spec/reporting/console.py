"""Rich console output for CLI."""

from __future__ import annotations

from rich.console import Console

from a2a_spec.diff.engine import DiffResult, DriftSeverity
from a2a_spec.pipeline.trace import PipelineTrace
from a2a_spec.policy.engine import PolicyResult
from a2a_spec.semantic.engine import SemanticResult
from a2a_spec.spec.validator import ValidationResult

console = Console()


SEVERITY_STYLES: dict[DriftSeverity, str] = {
    DriftSeverity.NONE: "green",
    DriftSeverity.LOW: "yellow",
    DriftSeverity.MEDIUM: "yellow bold",
    DriftSeverity.HIGH: "red",
    DriftSeverity.CRITICAL: "red bold",
}

# Text labels for severity — terminal-safe, no emoji or special Unicode.
SEVERITY_LABELS: dict[DriftSeverity, str] = {
    DriftSeverity.NONE: "PASS",
    DriftSeverity.LOW: "LOW ",
    DriftSeverity.MEDIUM: "WARN",
    DriftSeverity.HIGH: "FAIL",
    DriftSeverity.CRITICAL: "CRIT",
}


def print_validation_result(
    spec_name: str,
    scenario: str,
    structural: ValidationResult,
    policy_results: list[PolicyResult] | None = None,
    semantic_results: list[SemanticResult] | None = None,
    semantic_skipped: bool = False,
    expectation_errors: list[str] | None = None,
) -> None:
    """Print a single validation result."""
    overall = (
        structural.passed
        and all(p.passed for p in policy_results or [])
        and all(r.passed for r in semantic_results or [])
        and not expectation_errors
    )
    label = "PASS" if overall else "FAIL"
    color = "green" if overall else "red"

    parts: list[str] = [f"[{color}]{label}[/{color}] {spec_name} / {scenario}"]

    s_status = "[green]PASS[/green]" if structural.passed else "[red]FAIL[/red]"
    parts.append(f"  structural {s_status}")

    if not structural.passed:
        for error in structural.errors:
            parts.append(f"    [red]{error}[/red]")

    if policy_results:
        all_passed = all(p.passed for p in policy_results)
        p_status = "[green]PASS[/green]" if all_passed else "[red]FAIL[/red]"
        parts.append(f"  policy {p_status}")
        for p in policy_results:
            if not p.passed:
                parts.append(f"    [red]{p.rule_name}: {p.detail}[/red]")

    if semantic_results:
        all_passed = all(r.passed for r in semantic_results)
        m_status = "[green]PASS[/green]" if all_passed else "[red]FAIL[/red]"
        parts.append(f"  semantic {m_status}")
        for r in semantic_results:
            if not r.passed:
                parts.append(f"    [red]{r.rule_name}: {r.detail}[/red]")
    elif semantic_skipped:
        parts.append("  semantic [yellow]SKIPPED[/yellow] (disabled)")

    if expectation_errors:
        parts.append("  expectations [red]FAIL[/red]")
        for error in expectation_errors:
            parts.append(f"    [red]{error}[/red]")

    console.print("\n".join(parts))


def print_diff_results(
    agent_id: str,
    scenario: str,
    results: list[DiffResult],
) -> None:
    """Print semantic diff results."""
    if not results:
        console.print(f"  [green]PASS[/green] {agent_id} / {scenario}: No differences")
        return

    console.print(f"  {agent_id} / {scenario}:")
    for r in results:
        style = SEVERITY_STYLES.get(r.severity, "white")
        label = SEVERITY_LABELS.get(r.severity, r.severity.value.upper())
        console.print(f"    [{style}]{label}[/{style}] {r.field}: {r.explanation}")


def print_pipeline_trace(trace: PipelineTrace) -> None:
    """Print a pipeline execution trace."""
    status_label = "[green]PASS[/green]" if trace.passed else "[red]FAIL[/red]"
    console.print(f"\n  {status_label} Pipeline: {trace.pipeline_name} / {trace.scenario}")
    console.print(f"    Path: {' -> '.join(trace.path)}")
    console.print(f"    Latency: {trace.total_latency_ms:.0f}ms")

    for step in trace.steps:
        if step.spec_passed is None:
            step_label = "[dim]NO SPEC[/dim]"
        else:
            step_label = "[green]PASS[/green]" if step.spec_passed else "[red]FAIL[/red]"
        console.print(f"    {step_label} {step.agent_id} ({step.latency_ms:.0f}ms)")
        for error in step.spec_errors:
            console.print(f"        [red]{error}[/red]")


def print_summary(
    total: int,
    passed: int,
    failed: int,
    warnings: int = 0,
) -> None:
    """Print the final test summary bar."""
    console.print()
    console.rule()

    parts: list[str] = []
    if passed:
        parts.append(f"[green]{passed} passed[/green]")
    if failed:
        parts.append(f"[red]{failed} failed[/red]")
    if warnings:
        parts.append(f"[yellow]{warnings} warnings[/yellow]")

    console.print(f"  {' | '.join(parts)}  (total: {total})")
    console.rule()
