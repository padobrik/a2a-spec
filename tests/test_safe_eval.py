"""Tests for the sandboxed expression evaluator, including security vectors."""

from __future__ import annotations

import pytest

from a2a_spec._internal.safe_eval import safe_evaluate


class TestBasicExpressions:
    """Tests for supported expression types."""

    def test_simple_equality(self) -> None:
        """Simple == comparison must work."""
        assert safe_evaluate("output.category == 'billing'", {"output": {"category": "billing"}})

    def test_simple_inequality(self) -> None:
        """!= comparison must work."""
        assert safe_evaluate("output.priority != 'low'", {"output": {"priority": "high"}})

    def test_numeric_greater_than(self) -> None:
        """Numeric > comparison must work."""
        assert safe_evaluate("output.score > 0.5", {"output": {"score": 0.8}})

    def test_numeric_less_than(self) -> None:
        """Numeric < comparison must work."""
        assert safe_evaluate("output.score < 0.9", {"output": {"score": 0.5}})

    def test_numeric_lte(self) -> None:
        """<= comparison must work."""
        assert safe_evaluate("output.count <= 10", {"output": {"count": 10}})

    def test_numeric_gte(self) -> None:
        """>= comparison must work."""
        assert safe_evaluate("output.count >= 5", {"output": {"count": 5}})

    def test_boolean_and_both_true(self) -> None:
        """'and' must return True when both sides are True."""
        ctx = {"output": {"a": 1, "b": 2}}
        assert safe_evaluate("output.a == 1 and output.b == 2", ctx)

    def test_boolean_and_one_false(self) -> None:
        """'and' must return False when either side is False."""
        ctx = {"output": {"a": 1, "b": 99}}
        assert not safe_evaluate("output.a == 1 and output.b == 2", ctx)

    def test_boolean_or_first_true(self) -> None:
        """'or' must return True when first side is True."""
        ctx = {"output": {"a": 1}}
        assert safe_evaluate("output.a == 1 or output.a == 2", ctx)

    def test_boolean_or_both_false(self) -> None:
        """'or' must return False when both sides are False."""
        ctx = {"output": {"a": 3}}
        assert not safe_evaluate("output.a == 1 or output.a == 2", ctx)

    def test_subscript_access(self) -> None:
        """Subscript access output['key'] must work."""
        assert safe_evaluate("output['key'] == 'val'", {"output": {"key": "val"}})

    def test_false_comparison(self) -> None:
        """A False comparison must return False."""
        assert not safe_evaluate("output.x == 99", {"output": {"x": 1}})


class TestErrorCases:
    """Tests for expected errors on unsupported or unknown inputs."""

    def test_unknown_variable_raises(self) -> None:
        """Unknown top-level variable must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown variable"):
            safe_evaluate("foo == 1", {})

    def test_function_call_raises(self) -> None:
        """Function calls must be rejected."""
        with pytest.raises(ValueError, match="Unsupported"):
            safe_evaluate("len(output)", {"output": {"a": 1}})


class TestSecurityVectors:
    """Security tests — these expressions MUST all raise ValueError or SyntaxError."""

    def test_rejects_import_via_dunder(self) -> None:
        """__import__ call must be rejected."""
        with pytest.raises((ValueError, SyntaxError)):
            safe_evaluate("__import__('os').system('id')", {})

    def test_rejects_eval_call(self) -> None:
        """eval() call must be rejected."""
        with pytest.raises((ValueError, SyntaxError)):
            safe_evaluate("eval('1+1')", {})

    def test_rejects_exec_call(self) -> None:
        """exec() call must be rejected."""
        with pytest.raises((ValueError, SyntaxError)):
            safe_evaluate("exec('import os')", {})

    def test_rejects_lambda(self) -> None:
        """Lambda expressions must be rejected."""
        with pytest.raises((ValueError, SyntaxError)):
            safe_evaluate("(lambda: 1)()", {})

    def test_rejects_subclasses_traversal(self) -> None:
        """Class hierarchy traversal must be rejected."""
        with pytest.raises((ValueError, SyntaxError)):
            safe_evaluate("().__class__.__bases__[0].__subclasses__()", {})

    def test_rejects_list_comprehension_with_dunder(self) -> None:
        """List comprehensions over class hierarchy must be rejected."""
        with pytest.raises((ValueError, SyntaxError)):
            safe_evaluate("[x for x in ().__class__.__bases__]", {})

    def test_rejects_open_call(self) -> None:
        """File open() call must be rejected."""
        with pytest.raises((ValueError, SyntaxError)):
            safe_evaluate("open('/etc/passwd').read()", {})

    def test_rejects_unary_not(self) -> None:
        """Unary not operator (if unsupported) must be handled gracefully."""
        # 'not' is a UnaryOp in AST — currently unsupported, should raise
        with pytest.raises((ValueError, SyntaxError)):
            safe_evaluate("not output.x", {"output": {"x": True}})
