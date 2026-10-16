"""Small helpers for tree-sitter nodes of TypeScript and JavaScript code."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node


def node_key(node: Node) -> str | None:
    """The literal key of a member or subscript expression."""
    if node.type == "member_expression":
        prop = node.child_by_field_name("property")
        if prop is not None and prop.type == "property_identifier":
            return node_text(prop)
        return None
    index = node.child_by_field_name("index")
    return string_value(index) if index is not None else None


def is_optional(node: Node) -> bool:
    return node.child_by_field_name("optional_chain") is not None


def string_value(node: Node) -> str | None:
    """The value of a string literal without escapes or substitutions."""
    if node.type != "string":
        return None
    parts = node.named_children
    if any(p.type != "string_fragment" for p in parts):
        return None
    return "".join(node_text(p) for p in parts)


def first_error(node: Node) -> Node | None:
    if not node.has_error:
        return None
    if node.type == "ERROR" or node.is_missing:
        return node
    for child in node.children:
        found = first_error(child)
        if found is not None:
            return found
    return node


def node_text(node: Node) -> str:
    return (node.text or b"").decode("utf-8")


def node_line(node: Node) -> int:
    return node.start_point[0] + 1
