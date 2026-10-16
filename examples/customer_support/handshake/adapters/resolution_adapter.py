"""Resolution agent adapter for agent-handshake."""

from __future__ import annotations

from agent_handshake.adapters.function_adapter import FunctionAdapter

from agents.resolution import resolution_agent

resolution_adapter = FunctionAdapter(
    fn=resolution_agent,
    agent_id="resolution-agent",
    version="1.0.0",
)
