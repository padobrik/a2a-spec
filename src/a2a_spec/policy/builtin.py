"""Built-in policy validators."""

from __future__ import annotations

from typing import Any


def no_pii_in_output(output: dict[str, Any], input_data: dict[str, Any]) -> tuple[bool, str]:
    """Check that output doesn't contain common PII patterns.

    This is a basic check. For production PII detection,
    use a dedicated library like presidio.
    """
    import re

    pii_patterns = {
        "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "email": r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    }

    text = _dict_to_text(output)

    for name, pattern in pii_patterns.items():
        match = re.search(pattern, text)
        if match:
            return False, f"Potential {name} found: '{match.group()}'"

    return True, ""


def output_not_empty(output: dict[str, Any], input_data: dict[str, Any]) -> tuple[bool, str]:
    """Check that the output is not empty or trivially small."""
    if not output:
        return False, "Output is empty"

    text = _dict_to_text(output)
    if len(text.strip()) < 5:
        return False, f"Output content too short: '{text.strip()}'"

    return True, ""


def _dict_to_text(d: dict[str, Any]) -> str:
    """Flatten a dict to a single string for text-based checks."""
    parts: list[str] = []
    for value in d.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            parts.append(_dict_to_text(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(_dict_to_text(item))
    return " ".join(parts)
