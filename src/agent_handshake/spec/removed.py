"""Migration errors for spec content that was removed.

An old spec that still uses a removed rule must fail to load with a message
that says what to use instead, so it never passes silently.
"""

from __future__ import annotations

from typing import Any

REMOVED_IN = "0.9"

_REMOVED_VALIDATORS = {
    "agent_handshake.policy.builtin.no_pii_in_output": (
        "Use a regex policy rule with your own patterns, or a custom validator."
    ),
    "agent_handshake.policy.builtin.output_not_empty": (
        "List the fields the consumer needs in structural.required instead."
    ),
}


_REMOVED_SECTIONS = {
    "statistical": "It was never checked; delete the section.",
}


def removed_content(spec_data: dict[str, Any]) -> str | None:
    """The migration message for the first removed item in a raw spec, or None."""
    if "semantic" in spec_data:
        for rule in spec_data.get("semantic") or []:
            method = rule.get("method") if isinstance(rule, dict) else None
            if method:
                return (
                    f"Rule '{method}' was removed in {REMOVED_IN}. "
                    "Use a custom validator instead. See CHANGELOG.md."
                )
        return (
            f"Section 'semantic' was removed in {REMOVED_IN}. "
            "Delete it, or use a custom validator instead. See CHANGELOG.md."
        )
    for section, advice in _REMOVED_SECTIONS.items():
        if section in spec_data:
            return f"Section '{section}' was removed in {REMOVED_IN}. {advice} See CHANGELOG.md."
    for rule in spec_data.get("policy") or []:
        validator = rule.get("validator") if isinstance(rule, dict) else None
        if validator in _REMOVED_VALIDATORS:
            return (
                f"Validator '{validator}' was removed in {REMOVED_IN}. "
                f"{_REMOVED_VALIDATORS[validator]} See CHANGELOG.md."
            )
    return None
