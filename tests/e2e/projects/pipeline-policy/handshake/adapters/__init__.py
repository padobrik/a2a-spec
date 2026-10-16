from agents.resolution import resolve
from agents.triage import triage

from agent_handshake import FunctionAdapter

ADAPTERS = {
    "triage-agent": FunctionAdapter(fn=triage, agent_id="triage-agent", version="1"),
    "resolution-agent": FunctionAdapter(fn=resolve, agent_id="resolution-agent", version="1"),
}
