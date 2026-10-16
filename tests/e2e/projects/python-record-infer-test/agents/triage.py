"""Triage agent: classifies a support message without an LLM."""


async def triage(data: dict) -> dict:
    message = data["message"].lower()
    category = "billing" if "charge" in message else "general"
    return {
        "category": category,
        "priority": "high" if "urgent" in message else "low",
        "summary": data["message"][:80],
    }
