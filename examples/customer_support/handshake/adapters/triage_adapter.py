"""Triage agent adapter for agent-handshake."""

from __future__ import annotations

from agent_handshake.adapters.function_adapter import FunctionAdapter

from agents.triage import triage_agent

triage_adapter = FunctionAdapter(
    fn=triage_agent,
    agent_id="triage-agent",
    version="1.0.0",
)
