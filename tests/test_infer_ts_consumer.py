"""Tests for field-read analysis of TypeScript and JavaScript consumers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agent_handshake.exceptions import ConfigError
from agent_handshake.infer.consumer import analyze_consumer

pytest.importorskip("tree_sitter_typescript", reason="needs the typescript extra")


def _write(tmp_path: Path, code: str, name: str = "consumer.ts") -> Path:
    path = tmp_path / name
    path.write_text(code)
    return path


def _reads(path: Path, function: str = "agent") -> list[tuple[str, tuple[bool, ...]]]:
    return [(r.name, r.strict) for r in analyze_consumer(path, function).reads]


class TestReads:
    def test_member_subscript_optional_and_in(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "export async function agent(ticket: Triage): Promise<Reply> {\n"
            "  const tier = ticket.customer.tier;\n"
            '  const plan = ticket.billing?.plan ?? "free";\n'
            '  const p = ticket["priority"];\n'
            '  if ("vip" in ticket.customer) {}\n'
            "  return { tier, plan, p };\n"
            "}\n",
        )
        reads = analyze_consumer(path, "agent")
        assert reads.param == "ticket"
        assert [(r.name, r.line, r.strict) for r in reads.reads] == [
            ("customer.tier", 2, (True, False)),
            ("billing.plan", 3, (False, False)),
            ("priority", 4, (False,)),
            ("customer.vip", 5, (True, False)),
        ]
        assert reads.warnings == []

    def test_destructuring(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "function agent(t) {\n"
            '  const { priority, language = "en", meta: { source }, extra: { id } = {} } = t;\n'
            "  return [priority, language, source, id];\n"
            "}\n",
        )
        assert _reads(path) == [
            ("priority", (False,)),
            ("language", (False,)),
            ("meta.source", (True, False)),
            ("extra.id", (False, False)),
        ]

    def test_destructured_parameter_and_alias(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "export const agent = async ({ priority, customer }: T) => customer.tier + priority;\n",
        )
        assert _reads(path) == [
            ("priority", (False,)),
            ("customer", (False,)),
            ("customer.tier", (True, False)),
        ]

    def test_alias_of_nested_value(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "function agent(d) {\n  const c = d.customer;\n  return c?.tier;\n}\n",
        )
        assert _reads(path) == [("customer", (False,)), ("customer.tier", (False, False))]

    def test_string_and_array_members_are_not_fields(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "function agent(d) {\n"
            "  return [d.category.toLowerCase(), d.tags.length, d.tags[0], d.note?.trim()];\n"
            "}\n",
        )
        assert _reads(path) == [
            ("category", (True,)),
            ("tags", (True,)),
            ("tags", (True,)),
            ("note", (False,)),
        ]
        assert analyze_consumer(path, "agent").warnings == []

    def test_typescript_wrappers(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "function agent(d: unknown) { return (d as T).a!.b; }\n")
        assert _reads(path) == [("a.b", (True, False))]

    def test_writes_are_not_reads(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "function agent(d) { d.out = 1; return d.in; }\n")
        assert analyze_consumer(path, "agent").fields == ["in"]

    def test_this_parameter_skipped(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "function agent(this: Ctx, data: T) { return data.a; }\n")
        assert analyze_consumer(path, "agent").param == "data"

    @pytest.mark.parametrize(
        ("code", "function"),
        [
            ("const agent = data => data['a'];\n", "agent"),
            ("class A { run(input) { return input.a; } }\n", "run"),
            ("const agents = { resolve(d) { return d.a; } };\n", "resolve"),
            ("const agents = { other: (d) => d.a };\n", "other"),
            ("export default function agent(d) { return d.a; }\n", "agent"),
        ],
    )
    def test_function_forms(self, tmp_path: Path, code: str, function: str) -> None:
        assert analyze_consumer(_write(tmp_path, code), function).fields == ["a"]

    @pytest.mark.parametrize("suffix", [".mts", ".cts", ".tsx", ".js", ".mjs", ".cjs"])
    def test_every_suffix(self, tmp_path: Path, suffix: str) -> None:
        path = _write(tmp_path, "function agent(d) { return d.a; }\n", name=f"consumer{suffix}")
        assert analyze_consumer(path, "agent").fields == ["a"]

    def test_javascript_with_jsx(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "export function View(props) { return <div>{props.title}</div>; }\n",
            name="view.jsx",
        )
        assert analyze_consumer(path, "View").fields == ["title"]


class TestWarnings:
    @pytest.mark.parametrize(
        ("body", "message"),
        [
            ("return helper(d);", "'d' is used as a whole"),
            ("return Object.keys(d);", "'d' is used as a whole"),
            ("return { ...d };", "'d' is used as a whole"),
            ("return { d };", "'d' is used as a whole"),
            ("return d[key];", "'d' reads a non-literal key"),
            ("return d.customer[key];", "'customer' reads a non-literal key"),
            ('return d.hasOwnProperty("x");', "'d' calls .hasOwnProperty()"),
            ("const { a, ...rest } = d; return rest;", "'d' collects the remaining keys"),
            ("d = {}; return d;", "'d' is reassigned"),
            ("const c = d.customer; c.tier; return helper(c);", "'customer' is used as a whole"),
        ],
    )
    def test_untracked_use_warns(self, tmp_path: Path, body: str, message: str) -> None:
        path = _write(tmp_path, f"function agent(d, key) {{\n  {body}\n}}\n")
        warnings = analyze_consumer(path, "agent").warnings
        assert any(message in w for w in warnings), warnings
        assert all(w.startswith("line 2:") for w in warnings), warnings

    def test_leaf_alias_used_as_a_whole_does_not_warn(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "function agent(d) { const p = d.priority; return log(p); }\n")
        assert analyze_consumer(path, "agent").warnings == []


class TestErrors:
    def test_function_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            analyze_consumer(_write(tmp_path, "function other(d) {}\n"), "agent")

    def test_defined_twice(self, tmp_path: Path) -> None:
        code = "function agent(d) {}\nclass A { agent(d) {} }\n"
        with pytest.raises(ConfigError, match=r"more than once .*\(1, 2\)"):
            analyze_consumer(_write(tmp_path, code), "agent")

    def test_no_parameter(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="no input parameter"):
            analyze_consumer(_write(tmp_path, "function agent() {}\n"), "agent")

    def test_syntax_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="syntax error at line 2"):
            analyze_consumer(_write(tmp_path, "function agent(d) {\n  return d.;\n}\n"), "agent")

    def test_missing_extra(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "tree_sitter_typescript", None)
        path = _write(tmp_path, "function agent(d) { return d.a; }\n")
        with pytest.raises(ConfigError, match=r'pip install "agent-handshake\[typescript\]"'):
            analyze_consumer(path, "agent")
