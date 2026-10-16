"""Tests for consumer field-read analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_handshake.exceptions import ConfigError
from agent_handshake.infer.consumer import analyze_consumer, parse_source_ref


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

    def test_source_uses_posix_separators(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        path = tmp_path / "agents" / "consumer.py"
        path.write_text("def agent(d):\n    return d['a']\n")
        reads = analyze_consumer(path, "agent")
        assert reads.source == f"{path.as_posix()}:agent"
        assert "\\" not in reads.source

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

    def test_nested_reads(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "def agent(d):\n"
            "    tier = d['customer']['tier']\n"
            "    plan = d.get('billing', {}).get('plan')\n"
            "    vip = 'vip' in d['customer']\n"
            "    return tier, plan, vip\n",
        )
        reads = analyze_consumer(path, "agent")
        assert [(r.name, r.line, r.strict) for r in reads.reads] == [
            ("customer.tier", 2, (True, True)),
            ("billing.plan", 3, (False, False)),
            ("customer.vip", 4, (True, False)),
        ]
        assert reads.warnings == []

    def test_reads_through_alias(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "def agent(d):\n"
            "    customer = d['customer']\n"
            "    tier = customer.get('tier')\n"
            "    return tier.lower()\n",
        )
        reads = analyze_consumer(path, "agent")
        assert [(r.name, r.strict) for r in reads.reads] == [
            ("customer", (True,)),
            ("customer.tier", (True, False)),
        ]
        assert reads.warnings == []

    def test_rebound_alias_is_not_followed(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "def agent(d):\n    c = d['customer']\n    c = {}\n    return c['tier']\n",
        )
        assert analyze_consumer(path, "agent").fields == ["customer"]

    @pytest.mark.parametrize(
        ("body", "message"),
        [
            ("c = d['customer']\n    x = c['tier']\n    return helper(c)", "'customer' is used"),
            ("return d['customer'].items()", "'customer' calls .items()"),
            ("return d['customer'][key]", "'customer' reads a non-literal key"),
        ],
    )
    def test_untracked_nested_use_warns(self, tmp_path: Path, body: str, message: str) -> None:
        path = _write(tmp_path, f"def agent(d, key='k'):\n    {body}\n")
        warnings = analyze_consumer(path, "agent").warnings
        assert any(message in w for w in warnings), warnings

    @pytest.mark.parametrize(
        "body",
        [
            "t = d['tier']\n    return helper(t)",
            "return d['priority'].lower()",
            "return d['tags'][0]",
        ],
    )
    def test_leaf_values_do_not_warn(self, tmp_path: Path, body: str) -> None:
        path = _write(tmp_path, f"def agent(d):\n    {body}\n")
        assert analyze_consumer(path, "agent").warnings == []

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
