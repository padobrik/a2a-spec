"""Reads in helper functions of the same file, list items and fallbacks (phase 4.F)."""

from __future__ import annotations

from pathlib import Path

from agent_handshake.infer.consumer import analyze_consumer


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
