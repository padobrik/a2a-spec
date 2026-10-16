"""Triage agent: Claude classifies a support message into structured fields."""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import AsyncAnthropic

MODEL = os.environ.get("TRIAGE_MODEL", "claude-haiku-5-5")

# Structured output: the reply is JSON that matches this schema.
TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["billing", "shipping", "product", "account", "general"],
        },
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary": {
            "type": "string",
            "description": "One sentence that restates the customer's problem.",
        },
        "customer": {
            "type": "object",
            "properties": {
                "sentiment": {"type": "string", "enum": ["calm", "upset", "angry"]},
                "wants_refund": {"type": "boolean"},
            },
            "required": ["sentiment", "wants_refund"],
            "additionalProperties": False,
        },
    },
    "required": ["category", "priority", "summary", "customer"],
    "additionalProperties": False,
}

SYSTEM = (
    "You triage customer support messages for an online shop. "
    "Use high priority only when the customer says it is urgent or money was taken by mistake."
)


async def triage_agent(input_data: dict[str, Any]) -> dict[str, Any]:
    """Classify ``input_data["message"]`` with Claude and return the parsed JSON."""
    client = AsyncAnthropic()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": TRIAGE_SCHEMA}},
        messages=[{"role": "user", "content": input_data["message"]}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    result = json.loads(text)
    if not isinstance(result, dict):
        raise RuntimeError(f"{MODEL} returned {type(result).__name__}, not an object")
    return result
