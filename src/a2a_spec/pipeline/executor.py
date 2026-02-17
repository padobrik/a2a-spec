"""Execute pipeline tests with spec validation at each step."""

from __future__ import annotations

from typing import Any

from a2a_spec._internal.safe_eval import safe_evaluate
from a2a_spec.adapters.base import AgentAdapter
from a2a_spec.exceptions import PipelineExecutionError
from a2a_spec.pipeline.dag import PipelineDAG
from a2a_spec.pipeline.trace import AgentTraceStep, PipelineTrace
from a2a_spec.snapshot.replay import ReplayEngine
from a2a_spec.spec.registry import SpecRegistry
from a2a_spec.spec.validator import validate_output


class PipelineExecutor:
    """Executes a pipeline DAG for testing purposes.

    Can run in two modes:
    - "replay": Uses stored snapshots (deterministic, no LLM calls)
    - "live": Calls actual agents through adapters

    At each step, the output is validated against any applicable spec.
    """

    def __init__(
        self,
        dag: PipelineDAG,
        adapters: dict[str, AgentAdapter] | None = None,
        replay_engine: ReplayEngine | None = None,
        spec_registry: SpecRegistry | None = None,
    ) -> None:
        self.dag = dag
        self.adapters = adapters or {}
        self.replay = replay_engine
        self.specs = spec_registry

    async def execute(
        self,
        scenario: str,
        initial_input: dict[str, Any],
        mode: str = "replay",
    ) -> PipelineTrace:
        """Execute the pipeline for a given scenario.

        Args:
            scenario: Test scenario name.
            initial_input: Input data for entry agents.
            mode: "replay" or "live".

        Returns:
            PipelineTrace with full execution details.
        """
        trace = PipelineTrace(
            pipeline_name=self.dag.name,
            scenario=scenario,
        )

        order = self.dag.topological_order()
        outputs: dict[str, dict[str, Any]] = {}

        for agent_id in order:
            # Determine input for this agent
            predecessors = self.dag.predecessors(agent_id)

            if not predecessors:
                # Entry agent — use initial input
                agent_input = initial_input
            else:
                # Merge predecessor outputs, filtering by condition
                agent_input = {}
                for edge in predecessors:
                    pred_output = outputs.get(edge.from_agent)
                    if pred_output is None:
                        continue

                    # Evaluate edge condition
                    if edge.condition is not None:
                        if not safe_evaluate(edge.condition, {"output": pred_output}):
                            continue

                    agent_input[edge.from_agent] = pred_output

                # If no predecessors passed their conditions, skip this agent
                if not agent_input:
                    continue

                # Unwrap if single predecessor
                if len(agent_input) == 1:
                    agent_input = next(iter(agent_input.values()))

            # Execute agent
            output, latency = await self._call_agent(agent_id, scenario, agent_input, mode)
            outputs[agent_id] = output

            # Validate against specs
            spec_passed: bool | None = None
            spec_errors: list[str] = []
            if self.specs:
                for spec in self.specs.get_by_producer(agent_id):
                    result = validate_output(output, spec)
                    if not result.passed:
                        spec_passed = False
                        spec_errors.extend(result.errors)
                    elif spec_passed is None:
                        spec_passed = True

            trace.steps.append(
                AgentTraceStep(
                    agent_id=agent_id,
                    input_data=agent_input,
                    output_data=output,
                    latency_ms=latency,
                    spec_passed=spec_passed,
                    spec_errors=spec_errors,
                )
            )

        return trace

    async def _call_agent(
        self,
        agent_id: str,
        scenario: str,
        input_data: dict[str, Any],
        mode: str,
    ) -> tuple[dict[str, Any], float]:
        """Call an agent in either replay or live mode."""
        if mode == "replay":
            if self.replay is None:
                raise PipelineExecutionError(
                    agent_id, Exception("Replay mode requires a ReplayEngine")
                )
            output = self.replay.replay(agent_id, scenario)
            return output, 0.0

        # Live mode
        adapter = self.adapters.get(agent_id)
        if adapter is None:
            raise PipelineExecutionError(
                agent_id, Exception(f"No adapter registered for '{agent_id}'")
            )

        try:
            response = await adapter.call(input_data)
        except Exception as e:
            raise PipelineExecutionError(agent_id, e) from e

        return response.output, response.latency_ms or 0.0
