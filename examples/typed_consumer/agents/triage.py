"""Triage agent: classifies a support message. Plain Python, no model."""


async def triage_agent(data: dict) -> dict:
    text = data["message"].lower()
    return {
        "category": "billing" if "charge" in text else "general",
        "priority": "high" if "urgent" in text else "low",
        "summary": data["message"][:80],
    }
