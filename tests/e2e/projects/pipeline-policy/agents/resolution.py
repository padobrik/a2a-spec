async def resolve(ticket: dict) -> dict:
    return {"queue": ticket["category"]}
