"""Sandboxed expression evaluation for pipeline conditions.

SECURITY: This uses a restricted AST evaluator, NOT raw eval().
Only comparison operators, attribute access, and literals are allowed.
No function calls, imports, or assignments.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

# Allowed binary comparison operators
_OPERATORS: dict[type, Any] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

# Allowed boolean operators
_BOOL_OPS: dict[type, Any] = {
    ast.And: all,
    ast.Or: any,
}


class _SafeEvaluator(ast.NodeVisitor):
    """Restricted AST evaluator."""

    def __init__(self, context: dict[str, Any]) -> None:
        self.context = context

    def evaluate(self, expr: str) -> Any:
        """Evaluate an expression string against the context."""
        tree = ast.parse(expr, mode="eval")
        return self.visit(tree.body)

    def visit_Compare(self, node: ast.Compare) -> bool:
        """Handle comparison operations (==, !=, <, >, etc.)."""
        left = self.visit(node.left)
        for op_node, comparator in zip(node.ops, node.comparators):
            op_type = type(op_node)
            if op_type not in _OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type.__name__}")
            right = self.visit(comparator)
            if not _OPERATORS[op_type](left, right):
                return False
            left = right
        return True

    def visit_BoolOp(self, node: ast.BoolOp) -> bool:
        """Handle boolean operations (and, or)."""
        op_type = type(node.op)
        if op_type not in _BOOL_OPS:
            raise ValueError(f"Unsupported bool operator: {op_type.__name__}")
        values = [self.visit(v) for v in node.values]
        return bool(_BOOL_OPS[op_type](values))

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        """Handle attribute access (e.g., output.category)."""
        obj = self.visit(node.value)
        if isinstance(obj, dict):
            return obj.get(node.attr)
        return getattr(obj, node.attr, None)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        """Handle subscript access (e.g., output['key'])."""
        obj = self.visit(node.value)
        key = self.visit(node.slice)
        return obj[key]

    def visit_Name(self, node: ast.Name) -> Any:
        """Handle variable name resolution."""
        if node.id not in self.context:
            raise ValueError(f"Unknown variable: '{node.id}'")
        return self.context[node.id]

    def visit_Constant(self, node: ast.Constant) -> Any:
        """Handle literal values (strings, numbers, booleans)."""
        return node.value

    def visit_List(self, node: ast.List) -> list[Any]:
        """Handle list literals."""
        return [self.visit(el) for el in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> tuple[Any, ...]:
        """Handle tuple literals."""
        return tuple(self.visit(el) for el in node.elts)

    def generic_visit(self, node: ast.AST) -> None:
        """Reject any unsupported AST nodes."""
        raise ValueError(
            f"Unsupported expression element: {type(node).__name__}. "
            f"Only comparisons, attribute access, and literals are allowed."
        )


def safe_evaluate(expression: str, context: dict[str, Any]) -> Any:
    """Safely evaluate an expression against a context dict.

    Only supports: comparisons, boolean ops, attribute access,
    subscript access, and literals. No function calls or imports.

    Args:
        expression: The expression string (e.g., "output.category == 'billing'").
        context: Variables available in the expression.

    Returns:
        The evaluation result.

    Raises:
        ValueError: If the expression contains unsupported operations.
    """
    evaluator = _SafeEvaluator(context)
    return evaluator.evaluate(expression)
