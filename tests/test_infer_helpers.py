"""Reads in helper functions of the same file, list items and fallbacks (phase 4.F)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_handshake.cli.main import app
from agent_handshake.diff.consumers import rate_for_consumers
from agent_handshake.diff.engine import DiffEngine, DriftSeverity
from agent_handshake.infer.consumer import analyze_consumer
from agent_handshake.spec.loader import load_spec

runner = CliRunner()


def _analyze(tmp_path: Path, code: str, function: str = "run", suffix: str = ".py"):
    path = tmp_path / f"agent{suffix}"
    path.write_text(code)
    return analyze_consumer(path, function)


def _names(result) -> list[str]:
    return sorted({r.name for r in result.reads})


class TestPythonHelpers:
    def test_module_function_and_keyword_argument(self, tmp_path: Path) -> None:
        code = (
            "def run(state):\n"
            "    return _layout(state, task=state.get('task'))\n\n\n"
            "def _layout(s, task=None):\n"
            "    return s['title'], s.get('intro'), task.get('model')\n"
        )
        result = _analyze(tmp_path, code)
        assert _names(result) == ["intro", "task", "task.model", "title"]
        assert {r.line for r in result.reads if r.name == "title"} == {6}
        assert result.warnings == []

    def test_method_through_self(self, tmp_path: Path) -> None:
        code = (
            "class Agent:\n"
            "    async def run(self, state):\n"
            "        return await self.review(state)\n\n"
            "    async def review(self, draft_state):\n"
            "        return draft_state.get('draft'), draft_state['notes']\n"
        )
        assert _names(_analyze(tmp_path, code)) == ["draft", "notes"]

    def test_sub_dict_given_to_a_second_helper(self, tmp_path: Path) -> None:
        code = (
            "def run(state):\n"
            "    task = state.get('task')\n"
            "    return publish(task.get('formats'))\n\n\n"
            "def publish(formats):\n"
            "    return formats.get('pdf'), formats.get('docx')\n"
        )
        result = _analyze(tmp_path, code)
        assert _names(result) == ["task", "task.formats", "task.formats.docx", "task.formats.pdf"]

    def test_depth_is_limited_to_three(self, tmp_path: Path) -> None:
        code = (
            "def run(d):\n    return a(d)\n\n\n"
            "def a(d):\n    return b(d)\n\n\n"
            "def b(d):\n    return c(d)\n\n\n"
            "def c(d):\n    return e(d)\n\n\n"
            "def e(d):\n    return d['deep']\n"
        )
        result = _analyze(tmp_path, code)
        assert result.reads == []
        assert result.warnings == [
            "line 14: 'd' is used as a whole; the inferred contract may be incomplete"
        ]

    def test_recursive_helper_stops(self, tmp_path: Path) -> None:
        code = "def run(d):\n    return walk(d)\n\n\ndef walk(d):\n    return d['next'], walk(d)\n"
        result = _analyze(tmp_path, code)
        assert _names(result) == ["next"]

    def test_unknown_function_still_warns(self, tmp_path: Path) -> None:
        result = _analyze(tmp_path, "def run(d):\n    return helper(d)\n")
        assert result.warnings == [
            "line 2: 'd' is used as a whole; the inferred contract may be incomplete"
        ]


class TestPythonItemsAndFallbacks:
    def test_items_given_to_a_helper_method(self, tmp_path: Path) -> None:
        code = (
            "class M:\n"
            "    def run(self, plan):\n"
            "        return [self.search(item) for item in plan['searches'][:3]]\n\n"
            "    def search(self, item):\n"
            "        return item['query'], item.get('reason')\n"
        )
        result = _analyze(tmp_path, code)
        assert _names(result) == ["searches", "searches[].query", "searches[].reason"]
        assert result.warnings == []

    def test_items_given_to_an_unknown_function_warn(self, tmp_path: Path) -> None:
        code = "def run(d):\n    for r in d['rs']:\n        send(r)\n"
        assert _analyze(tmp_path, code).warnings == [
            "line 3: 'r' is an item of 'rs' and goes to a function that is not followed; "
            "the inferred contract may be incomplete"
        ]

    def test_fallback_inside_an_if_keeps_the_alias(self, tmp_path: Path) -> None:
        code = (
            "def run(state):\n"
            "    headers = state.get('headers') or {}\n"
            "    if not isinstance(headers, dict):\n"
            "        headers = {}\n"
            "    return headers.get('title')\n"
        )
        assert _names(_analyze(tmp_path, code)) == ["headers", "headers.title"]

    def test_loop_over_a_fallback(self, tmp_path: Path) -> None:
        code = "def run(d):\n    return [s['name'] for s in (d.get('sections') or [])]\n"
        assert _names(_analyze(tmp_path, code)) == ["sections", "sections[].name"]


class TestTypeScriptHelpers:
    @pytest.fixture(autouse=True)
    def _needs_typescript(self) -> None:
        pytest.importorskip("tree_sitter_typescript", reason="needs the typescript extra")

    def test_function_and_method_helpers(self, tmp_path: Path) -> None:
        code = (
            "function layout(s) { return s.title + s.intro; }\n"
            "class M {\n"
            "  run(state) { return layout(state) + this.review(state.draft); }\n"
            "  review(draft) { return draft.notes; }\n"
            "}\n"
        )
        result = _analyze(tmp_path, code, suffix=".ts")
        assert _names(result) == ["draft", "draft.notes", "intro", "title"]

    def test_items_given_to_a_method(self, tmp_path: Path) -> None:
        code = (
            "class M {\n"
            "  run(plan) {\n"
            "    const searches = plan.searches.slice(0, 3);\n"
            "    return searches.map(async (item) => this.search(item));\n"
            "  }\n"
            "  search(item) { return `${item.query} ${item.reason}`; }\n"
            "}\n"
        )
        result = _analyze(tmp_path, code, suffix=".ts")
        assert _names(result) == ["searches", "searches[].query", "searches[].reason"]
        assert result.warnings == []

    def test_nullish_fallback(self, tmp_path: Path) -> None:
        code = "function run(d) {\n  const h = d.headers ?? {};\n  return h.title;\n}\n"
        assert _names(_analyze(tmp_path, code, suffix=".ts")) == ["headers", "headers.title"]


SNAPSHOT = {
    "schema_version": 1,
    "agent_id": "planner",
    "scenario": "s",
    "input": {},
    "output": {"searches": [{"query": "q1", "reason": "r1"}, {"query": "q2", "reason": "r2"}]},
}


def test_items_end_to_end(tmp_path: Path) -> None:
    snaps = tmp_path / "snapshots" / "planner"
    snaps.mkdir(parents=True)
    (snaps / "s_1.json").write_text(json.dumps(SNAPSHOT))
    (tmp_path / "consumer.py").write_text(
        "def run(plan):\n    return [item['query'] for item in plan['searches']]\n"
    )
    config = tmp_path / "handshake.yaml"
    config.write_text(
        f'project_name: t\nspecs_dir: "{(tmp_path / "specs").as_posix()}"\n'
        f'storage:\n  path: "{(tmp_path / "snapshots").as_posix()}"\n'
    )
    base = ["--config", str(config)]
    infer = ["infer", *base, "--producer", "planner", "--consumer", "search"]
    result = runner.invoke(app, [*infer, "--source", f"{tmp_path / 'consumer.py'}:run"])
    assert result.exit_code == 0, result.output

    spec = load_spec(tmp_path / "specs" / "planner-to-search.yaml")
    searches = spec.structural.properties["searches"]
    assert searches["type"] == "array"
    assert searches["items"]["required"] == ["query"]
    assert spec.read_at["searches[].query"] == [2]
    assert runner.invoke(app, ["infer", "--check", *base]).exit_code == 0
    assert runner.invoke(app, ["test", *base]).exit_code == 0

    # The producer drops query from one item: the spec catches it.
    broken = {**SNAPSHOT, "output": {"searches": [{"reason": "r1"}]}}
    (snaps / "s_1.json").write_text(json.dumps(broken))
    assert runner.invoke(app, ["test", *base]).exit_code == 1

    # diff names the reader of a field inside the items.
    results = DiffEngine().diff(SNAPSHOT["output"], {"other": 1})
    rated = rate_for_consumers(results, [spec])
    removed = next(r for r in rated if r.field == "searches")
    assert removed.severity == DriftSeverity.HIGH
    # Specs keep POSIX paths, so they read the same on every OS.
    consumer = (tmp_path / "consumer.py").as_posix()
    assert removed.explanation.endswith(f"search reads it at {consumer}:2")
