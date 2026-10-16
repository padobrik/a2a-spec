"""Key paths that a spec names in its structural schema."""

from __future__ import annotations

from typing import Any

from agent_handshake.infer.paths import ITEMS
from agent_handshake.spec.schema import Spec


def spec_schema(spec: Spec) -> dict[str, Any]:
    """The structural part of a spec as one JSON Schema object."""
    return {"required": spec.structural.required, "properties": spec.structural.properties}


def field_paths(schema: Any, parent: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """Every key path the schema names, parents before children.

    Keys of list items are under ``ITEMS``: ``("searches", "[]", "query")``.
    """
    paths: list[tuple[str, ...]] = []
    properties = schema_dict(schema, "properties")
    for key in dict.fromkeys([*schema_list(schema, "required"), *properties]):
        path = (*parent, key)
        paths.append(path)
        paths += field_paths(properties.get(key), path)
        items = schema_dict(properties.get(key), "items")
        if items:
            paths += field_paths(items, (*path, ITEMS))
    return paths


def schema_list(schema: Any, key: str) -> list[Any]:
    """``schema[key]`` if it is a list, else an empty list."""
    value = schema.get(key) if isinstance(schema, dict) else None
    return value if isinstance(value, list) else []


def schema_dict(schema: Any, key: str) -> dict[str, Any]:
    """``schema[key]`` if it is a dict, else an empty dict."""
    value = schema.get(key) if isinstance(schema, dict) else None
    return value if isinstance(value, dict) else {}
