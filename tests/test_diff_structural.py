"""Tests for structural diff."""

from __future__ import annotations

from a2a_spec.diff.structural import structural_diff


class TestStructuralDiff:
    def test_identical_dicts(self) -> None:
        diffs = structural_diff({"a": 1}, {"a": 1})
        assert diffs == []

    def test_added_field(self) -> None:
        diffs = structural_diff({}, {"new": "value"})
        assert len(diffs) == 1
        assert diffs[0].change_type == "added"
        assert diffs[0].field == "new"

    def test_removed_field(self) -> None:
        diffs = structural_diff({"old": "value"}, {})
        assert len(diffs) == 1
        assert diffs[0].change_type == "removed"
        assert diffs[0].field == "old"

    def test_changed_value(self) -> None:
        diffs = structural_diff({"x": "old"}, {"x": "new"})
        assert len(diffs) == 1
        assert diffs[0].change_type == "changed"
        assert diffs[0].old_value == "old"
        assert diffs[0].new_value == "new"

    def test_type_changed(self) -> None:
        diffs = structural_diff({"x": "string"}, {"x": 42})
        assert len(diffs) == 1
        assert diffs[0].change_type == "type_changed"

    def test_nested_diff(self) -> None:
        old = {"outer": {"inner": "old"}}
        new = {"outer": {"inner": "new"}}
        diffs = structural_diff(old, new)
        assert len(diffs) == 1
        assert diffs[0].field == "outer.inner"
        assert diffs[0].change_type == "changed"

    def test_multiple_changes(self) -> None:
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1, "b": 99, "d": 4}
        diffs = structural_diff(old, new)
        fields = {d.field for d in diffs}
        assert "b" in fields
        assert "c" in fields
        assert "d" in fields

    def test_empty_dicts(self) -> None:
        diffs = structural_diff({}, {})
        assert diffs == []
