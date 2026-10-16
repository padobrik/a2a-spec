"""The agents agent-handshake records. Only the triage agent calls an LLM."""

from agent_handshake import FunctionAdapter

from agents.triage import MODEL, triage_agent

ADAPTERS = {
    "triage-agent": FunctionAdapter(fn=triage_agent, agent_id="triage-agent", version=MODEL),
}
