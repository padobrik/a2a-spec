"""Resolution agent: gets the user's query and the triage ticket as a Pydantic model."""

from agents.models import Ticket


async def resolution_agent(query: str, ticket: Ticket) -> dict:
    queue = "billing" if ticket.category == "billing" else "general"
    urgent = getattr(ticket, "priority", "low") == "high"
    return {"queue": queue, "escalate": urgent, "reply": f"About: {query}"}
