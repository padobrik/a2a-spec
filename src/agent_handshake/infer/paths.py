"""Field paths as text: ``customer.tier``, and ``searches[].query`` for list items."""

from __future__ import annotations

# The path segment that stands for "each item of the list".
ITEMS = "[]"


def dotted(path: tuple[str, ...]) -> str:
    """``("searches", "[]", "query")`` as ``searches[].query``."""
    text = ""
    for key in path:
        text += key if key == ITEMS else (f".{key}" if text else key)
    return text
