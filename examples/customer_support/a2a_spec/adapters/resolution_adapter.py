"""Resolution agent adapter for a2a-spec."""

from __future__ import annotations

from a2a_spec.adapters.function_adapter import FunctionAdapter

from examples.customer_support.agents.resolution import resolution_agent

resolution_adapter = FunctionAdapter(
    fn=resolution_agent,
    agent_id="resolution-agent",
    version="1.0.0",
)
