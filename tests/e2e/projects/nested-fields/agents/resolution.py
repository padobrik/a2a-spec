async def resolve(ticket: dict) -> dict:
    customer = ticket["customer"]
    return {"priority_support": customer.get("tier") == "pro"}
