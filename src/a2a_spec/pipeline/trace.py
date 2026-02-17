"""Pipeline execution trace model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentTraceStep:
    """A single agent execution within a pipeline trace."""

    agent_id: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    latency_ms: float
    spec_passed: bool | None = None
    spec_errors: list[str] = field(default_factory=list)


@dataclass
class PipelineTrace:
    """Full execution trace of a pipeline run."""

    pipeline_name: str
    scenario: str
    steps: list[AgentTraceStep] = field(default_factory=list)
    invariant_results: list[dict[str, Any]] = field(default_factory=list)

    @property
    def path(self) -> list[str]:
        """Ordered list of agent IDs that were executed."""
        return [s.agent_id for s in self.steps]

    @property
    def outputs(self) -> dict[str, dict[str, Any]]:
        """Map of agent_id -> output_data."""
        return {s.agent_id: s.output_data for s in self.steps}

    @property
    def total_latency_ms(self) -> float:
        """Total latency across all steps."""
        return sum(s.latency_ms for s in self.steps)

    @property
    def all_specs_passed(self) -> bool:
        """Whether all spec validations passed."""
        return all(s.spec_passed is True for s in self.steps if s.spec_passed is not None)

    @property
    def all_invariants_passed(self) -> bool:
        """Whether all invariant checks passed."""
        return all(r.get("passed", False) for r in self.invariant_results)

    @property
    def passed(self) -> bool:
        """Whether the entire pipeline trace passed."""
        return self.all_specs_passed and self.all_invariants_passed

    def summary(self) -> str:
        """One-line summary of the trace."""
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Pipeline '{self.pipeline_name}' / '{self.scenario}': {status} "
            f"({len(self.steps)} agents, {self.total_latency_ms:.0f}ms)"
        )
