async def resolve(ticket: dict) -> dict:
    return {"queue": ticket["category"], "reply_in": ticket.get("language", "en")}
