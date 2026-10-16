"""Tests for consumer field-read analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from a2a_spec.exceptions import ConfigError
from a2a_spec.infer.consumer import analyze_consumer, parse_source_ref


def _write(tmp_path: Path, code: str) -> Path:
    path = tmp_path / "consumer.py"
    path.write_text(code)
    return path


class TestAnalyzeConsumer:
    def test_strict_and_optional_reads(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "async def agent(data: dict) -> dict:\n"
            "    a = data['category']\n"
            "    b = data.get('priority', 'medium')\n"
            "    if 'notes' in data:\n"
            "        pass\n"
            "    return {'x': a, 'y': b}\n",
        )
        reads = analyze_consumer(path, "agent")
        assert reads.param == "data"
        assert [(r.name, r.line, r.strict) for r in reads.reads] == [
            ("category", 2, (True,)),
            ("priority", 3, (False,)),
            ("notes", 4, (False,)),
        ]
        assert reads.warnings == []

    def test_fields_deduplicated_in_order(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "def agent(d):\n    return d.get('b'), d['a'], d['b']\n")
        assert analyze_consumer(path, "agent").fields == ["b", "a"]

    def test_method_skips_self(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "class A:\n    def run(self, inp):\n        return inp['k']\n")
        reads = analyze_consumer(path, "run")
        assert reads.param == "inp"
        assert reads.fields == ["k"]

    def test_writes_are_not_reads(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "def agent(d):\n    d['out'] = 1\n    return d['in']\n")
        assert analyze_consumer(path, "agent").fields == ["in"]

    @pytest.mark.parametrize(
        ("body", "message"),
        [
            ("return helper(d)", "is used as a whole"),
            ("return d[key]", "non-literal key"),
            ("return d.get(key)", "non-literal key"),
            ("return list(d.items())", "calls .items()"),
            ("d = {}\n    return d", "is reassigned"),
        ],
    )
    def test_untracked_use_warns(self, tmp_path: Path, body: str, message: str) -> None:
        path = _write(tmp_path, f"def agent(d, key='k'):\n    {body}\n")
        warnings = analyze_consumer(path, "agent").warnings
        assert any(message in w for w in warnings), warnings
        assert all("line 2" in w or "line 3" in w for w in warnings)

    def test_function_not_found(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "def other(d):\n    pass\n")
        with pytest.raises(ConfigError, match="not found"):
            analyze_consumer(path, "agent")

    def test_ambiguous_function(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path, "def agent(d):\n    pass\nclass A:\n    def agent(self, d):\n        pass\n"
        )
        with pytest.raises(ConfigError, match="more than once"):
            analyze_consumer(path, "agent")

    def test_no_parameter(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "def agent():\n    pass\n")
        with pytest.raises(ConfigError, match="no input parameter"):
            analyze_consumer(path, "agent")

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            analyze_consumer(tmp_path / "nope.py", "agent")

    def test_syntax_error(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "def agent(:\n")
        with pytest.raises(ConfigError, match="Cannot parse"):
            analyze_consumer(path, "agent")


class TestParseSourceRef:
    def test_valid(self) -> None:
        assert parse_source_ref("agents/res.py:run") == (Path("agents/res.py"), "run")

    @pytest.mark.parametrize("ref", ["agents/res.py", ":run", "agents/res.py:"])
    def test_invalid(self, ref: str) -> None:
        with pytest.raises(ConfigError, match="path/to/file.py:function"):
            parse_source_ref(ref)
