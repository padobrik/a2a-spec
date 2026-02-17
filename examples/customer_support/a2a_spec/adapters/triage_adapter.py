"""Triage agent adapter for a2a-spec."""

from __future__ import annotations

from a2a_spec.adapters.function_adapter import FunctionAdapter

from examples.customer_support.agents.triage import triage_agent

triage_adapter = FunctionAdapter(
    fn=triage_agent,
    agent_id="triage-agent",
    version="1.0.0",
)
