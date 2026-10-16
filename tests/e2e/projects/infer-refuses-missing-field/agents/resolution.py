async def resolve(ticket: dict) -> dict:
    escalate = ticket.get("priority", "low") == "high"
    return {"queue": ticket["category"], "escalate": escalate}
