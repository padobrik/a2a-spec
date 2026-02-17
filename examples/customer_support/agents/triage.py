"""Triage agent — classifies support tickets by category and priority."""

from __future__ import annotations


async def triage_agent(input_data: dict) -> dict:
    """Classify a customer support message.

    In a real implementation, this would call an LLM like OpenAI GPT-4.
    For this example, we use simple keyword matching.

    Args:
        input_data: Dict with 'message' key containing customer message.

    Returns:
        Dict with category, summary, priority, and confidence.
    """
    message = input_data.get("message", "").lower()

    # Simple keyword-based classification
    if any(word in message for word in ["charge", "bill", "payment", "invoice", "refund"]):
        category = "billing"
    elif any(word in message for word in ["ship", "deliver", "track", "package"]):
        category = "shipping"
    elif any(word in message for word in ["product", "broken", "defect", "quality"]):
        category = "product"
    else:
        category = "general"

    # Generate summary
    summary = f"Customer reports issue related to {category}: {message[:100]}"

    return {
        "category": category,
        "summary": summary,
        "priority": "high" if "urgent" in message else "medium",
        "confidence": 0.92,
    }
