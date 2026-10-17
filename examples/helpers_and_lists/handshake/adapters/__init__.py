from agents.planner import planner_agent

from agent_handshake import FunctionAdapter

ADAPTERS = {
    "planner-agent": FunctionAdapter(fn=planner_agent, agent_id="planner-agent", version="1.0"),
}
