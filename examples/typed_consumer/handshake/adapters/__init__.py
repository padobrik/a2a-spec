from agents.triage import triage_agent

from agent_handshake import FunctionAdapter

ADAPTERS = {
    "triage-agent": FunctionAdapter(fn=triage_agent, agent_id="triage-agent", version="1.0"),
}
