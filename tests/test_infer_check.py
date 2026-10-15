"""Tests for checking inferred specs against consumer code."""

from __future__ import annotations

from pathlib import Path

import pytest

from a2a_spec.exceptions import ConfigError
from a2a_spec.infer.check import check_inferred_spec
from a2a_spec.spec.schema import Spec, StructuralSpec


def _spec(source: str | None, required: list[str], props: list[str]) -> Spec:
    return Spec(
        name="t2r",
        version="1.0",
        producer="triage",
        consumer="res",
        inferred_from=source,
        structural=StructuralSpec(required=required, properties={p: {} for p in props}),
    )


def _consumer(tmp_path: Path, body: str) -> str:
    path = tmp_path / "res.py"
    path.write_text(f"def run(data):\n    {body}\n")
    return f"{path}:run"


class TestCheckInferredSpec:
    def test_up_to_date(self, tmp_path: Path) -> None:
        src = _consumer(tmp_path, "return data['category'], data.get('priority')")
        result = check_inferred_spec(_spec(src, ["category", "priority"], ["category", "priority"]))
        assert result.passed and result.warnings == []

    def test_new_field_read_fails(self, tmp_path: Path) -> None:
        src = _consumer(tmp_path, "return data['category'], data.get('urgency')")
        result = check_inferred_spec(_spec(src, ["category"], ["category"]))
        assert result.failures == ["run reads 'urgency' (line 2), which the spec does not cover"]

    def test_strict_read_of_optional_field_fails(self, tmp_path: Path) -> None:
        src = _consumer(tmp_path, "return data['priority']")
        result = check_inferred_spec(_spec(src, [], ["priority"]))
        assert "with [] (line 2), but the spec makes it optional" in result.failures[0]

    def test_optional_read_of_optional_field_passes(self, tmp_path: Path) -> None:
        src = _consumer(tmp_path, "return data.get('priority')")
        assert check_inferred_spec(_spec(src, [], ["priority"])).passed

    def test_field_no_longer_read_warns(self, tmp_path: Path) -> None:
        src = _consumer(tmp_path, "return data['category']")
        result = check_inferred_spec(_spec(src, ["category", "priority"], ["category", "priority"]))
        assert result.passed
        assert result.warnings == ["the spec covers 'priority', which run no longer reads"]

    def test_partial_analysis_warns(self, tmp_path: Path) -> None:
        src = _consumer(tmp_path, "return helper(data)")
        result = check_inferred_spec(_spec(src, [], []))
        assert any("is used as a whole" in w for w in result.warnings)

    def test_not_inferred(self) -> None:
        with pytest.raises(ValueError, match="was not inferred"):
            check_inferred_spec(_spec(None, [], []))

    def test_missing_consumer(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            check_inferred_spec(_spec(f"{tmp_path / 'gone.py'}:run", [], []))
