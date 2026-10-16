from agents.triage import triage

from agent_handshake import FunctionAdapter

ADAPTERS = {"triage-agent": FunctionAdapter(fn=triage, agent_id="triage-agent", version="1")}
