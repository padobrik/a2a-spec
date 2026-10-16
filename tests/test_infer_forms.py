"""Every supported read form and every warning of handshake infer, in Python and TypeScript.

Each case is the smallest consumer that uses the form; the expected value is
(dotted path, strictness per key). Warnings must carry the line number.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent_handshake.infer.consumer import analyze_consumer

PY_FORMS = [
    ("subscript", "return d['a']", [("a", (True,))]),
    ("get", "return d.get('a')", [("a", (False,))]),
    ("get with default", "return d.get('a', 'x')", [("a", (False,))]),
    ("in", "return 'a' in d", [("a", (False,))]),
    ("nested subscript", "return d['a']['b']", [("a.b", (True, True))]),
    ("nested get", "return d.get('a', {}).get('b')", [("a.b", (False, False))]),
    ("in on nested", "return 'b' in d['a']", [("a.b", (True, False))]),
    ("alias", "a = d['a']\n    return a.get('b')", [("a", (True,)), ("a.b", (True, False))]),
    ("method of a list item", "return [t.upper() for t in d['tags']]", [("tags", (True,))]),
    ("attribute of a nested value", "return d['date'].year", [("date", (True,))]),
    (
        "comprehension name is local",
        "r = d['a']\n    xs = [r for r in d['rs']]\n    return r.get('b'), xs",
        [("a", (True,)), ("rs", (True,)), ("a.b", (True, False))],
    ),
]

TS_FORMS = [
    ("member", "return d.a;", [("a", (False,))]),
    ("subscript", 'return d["a"];', [("a", (False,))]),
    ("optional chaining", "return d.a?.b;", [("a.b", (False, False))]),
    ("nested member", "return d.a.b;", [("a.b", (True, False))]),
    ("in", 'return "a" in d;', [("a", (False,))]),
    ("destructuring", "const { a } = d; return a;", [("a", (False,))]),
    ("destructuring default", "const { a = 1 } = d; return a;", [("a", (False,))]),
    ("nested destructuring", "const { a: { b } } = d; return b;", [("a.b", (True, False))]),
    ("alias", "const a = d.a; return a.b;", [("a", (False,)), ("a.b", (True, False))]),
    ("length of a list item", "return d.tags.map(t => t.length);", [("tags", (True,))]),
    ("method of a list item", "return d.tags.map(t => t.trim());", [("tags", (True,))]),
    (
        "callback name is local",
        "const item = d.customer; d.tags.map(item => item.length); return item.name;",
        [("customer", (False,)), ("tags", (True,)), ("customer.name", (True, False))],
    ),
]

PY_WARNINGS = [
    ("whole use", "return helper(d)", "'d' is used as a whole"),
    ("non-literal key", "return d[key]", "'d' reads a non-literal key"),
    ("non-literal get", "return d.get(key)", "'d' calls .get() with a non-literal key"),
    ("method on input", "return d.items()", "'d' calls .items()"),
    ("reassignment", "d = {}\n    return d", "'d' is reassigned"),
    ("alias whole use", "a = d['a']\n    a['b']\n    return helper(a)", "'a' is used as a whole"),
    ("alias through or", "a = d.get('a') or {}\n    return a.get('b')", "holds 'a' through `or`"),
    ("alias through if", "a = d['a'] if key else {}\n    return a['b']", "a conditional"),
    ("loop item", "for r in d['rs']:\n        r['x']\n    return 1", "'r' is an item of 'rs'"),
    ("comprehension item", "return [r['x'] for r in d['rs']]", "'r' is an item of 'rs'"),
    ("item passed on", "for r in d['rs']:\n        h(r)\n    return 1", "'r' is an item of 'rs'"),
    ("item read by index", "return d['rs'][0]['x']", "an item of 'rs' is read"),
    ("attribute", "return d.spam", "'d' reads the attribute .spam, which is not followed yet"),
]

TS_WARNINGS = [
    ("whole use", "return helper(d);", "'d' is used as a whole"),
    ("non-literal key", "return d[key];", "'d' reads a non-literal key"),
    ("method on input", "return d.hasOwnProperty('a');", "'d' calls .hasOwnProperty()"),
    ("rest pattern", "const { a, ...rest } = d; return rest;", "'d' collects the remaining keys"),
    ("computed key", "const { [key]: v } = d; return v;", "'d' destructures a non-literal key"),
    ("reassignment", "d = {}; return d;", "'d' is reassigned"),
    ("alias whole use", "const a = d.a; a.b; return helper(a);", "'a' is used as a whole"),
    ("for-of item", "for (const r of d.rs) { r.x; } return 1;", "'r' is an item of 'rs'"),
    ("map callback item", "return d.rs.map(r => r.x);", "'r' is an item of 'rs'"),
    ("item of a copy", "const s = d.rs.slice(0, 2); return s.map(r => f(r));", "item of 'rs'"),
    ("reduce item", "return d.rs.reduce((a, r) => a + r.v, 0);", "'r' is an item of 'rs'"),
    ("item read by index", "return d.rs[0].x;", "an item of 'rs' is read"),
]


def _py(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "consumer.py"
    path.write_text(f"def agent(d, key='k'):\n    {body}\n")
    return path


def _ts(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "consumer.ts"
    path.write_text(f"function agent(d, key) {{\n  {body}\n}}\n")
    return path


def _reads(path: Path) -> list[tuple[str, tuple[bool, ...]]]:
    return [(r.name, r.strict) for r in analyze_consumer(path, "agent").reads]


@pytest.mark.parametrize(("form", "body", "expected"), PY_FORMS, ids=[f[0] for f in PY_FORMS])
def test_python_form(tmp_path: Path, form: str, body: str, expected: list[object]) -> None:
    path = _py(tmp_path, body)
    assert _reads(path) == expected
    assert analyze_consumer(path, "agent").warnings == []


@pytest.mark.parametrize(("form", "body", "expected"), TS_FORMS, ids=[f[0] for f in TS_FORMS])
def test_typescript_form(tmp_path: Path, form: str, body: str, expected: list[object]) -> None:
    pytest.importorskip("tree_sitter_typescript", reason="needs the typescript extra")
    path = _ts(tmp_path, body)
    assert _reads(path) == expected
    assert analyze_consumer(path, "agent").warnings == []


@pytest.mark.parametrize(("kind", "body", "message"), PY_WARNINGS, ids=[w[0] for w in PY_WARNINGS])
def test_python_warning(tmp_path: Path, kind: str, body: str, message: str) -> None:
    warnings = analyze_consumer(_py(tmp_path, body), "agent").warnings
    assert any(message in w for w in warnings), warnings
    assert all(w.split(":")[0].startswith("line ") for w in warnings), warnings


@pytest.mark.parametrize(("kind", "body", "message"), TS_WARNINGS, ids=[w[0] for w in TS_WARNINGS])
def test_typescript_warning(tmp_path: Path, kind: str, body: str, message: str) -> None:
    pytest.importorskip("tree_sitter_typescript", reason="needs the typescript extra")
    warnings = analyze_consumer(_ts(tmp_path, body), "agent").warnings
    assert any(message in w for w in warnings), warnings
    assert all(w.startswith("line 2:") for w in warnings), warnings


INFER_PROJECT = {
    "handshake.yaml": "project_name: t\n",
    "agents/resolution.py": (
        "def resolve(t):\n"
        "    c = t['customer']\n"
        "    return t.get('priority'), c.get('tier'), 'vip' in c, t['category']\n"
    ),
    "handshake/snapshots/triage/a_1.json": (
        '{"schema_version": 1, "agent_id": "triage", "scenario": "a", "input": {},'
        ' "output": {"category": "billing", "priority": "high",'
        ' "customer": {"tier": "pro", "vip": true}}}'
    ),
}


def _infer(root: Path, out: str, seed: str) -> bytes:
    for name, content in INFER_PROJECT.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(content)
    script = Path(sys.executable).parent / "handshake"
    command = [str(script) if script.exists() else "handshake"]
    command += ["infer", "--producer", "triage", "--consumer", "resolution"]
    command += ["--source", "agents/resolution.py:resolve", "--out", out]
    env = {**os.environ, "PYTHONHASHSEED": seed}
    subprocess.run(command, cwd=root, env=env, check=True, capture_output=True)
    return (root / out).read_bytes()


def test_infer_output_is_byte_identical_across_runs(tmp_path: Path) -> None:
    """Runs in separate processes with different hash seeds give the same YAML."""
    outputs = {_infer(tmp_path, f"spec{seed}.yaml", seed) for seed in ("0", "1", "12345")}
    assert len(outputs) == 1
    assert b"read_at:" in outputs.pop()
