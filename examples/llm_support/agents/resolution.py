"""Resolution agent: plain code that acts on the triage result."""

from __future__ import annotations

from typing import Any


async def resolution_agent(ticket: dict[str, Any]) -> dict[str, Any]:
    """Decide how to handle a triaged ticket."""
    customer = ticket.get("customer", {})
    escalate = ticket.get("priority", "low") == "high" or customer.get("sentiment") == "angry"
    queue = {"billing": "payments", "shipping": "logistics"}.get(ticket["category"], "support")
    return {
        "queue": queue,
        "escalate": escalate,
        "offer_refund": bool(customer.get("wants_refund")) and ticket["category"] == "billing",
    }
