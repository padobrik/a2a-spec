"""Tests for the script that scores consumer analysis on the recon benchmark."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "benchmark.py"
_spec = importlib.util.spec_from_file_location("benchmark", SCRIPT)
assert _spec is not None
assert _spec.loader is not None
benchmark = importlib.util.module_from_spec(_spec)
# Dataclasses look up their module in sys.modules while the class is built.
sys.modules["benchmark"] = benchmark
_spec.loader.exec_module(benchmark)

CONSUMER = (
    "def run(state):\n    task = state['task']\n    return task.get('model'), state.get('extra')\n"
)


def _case(**fields: object) -> dict[str, object]:
    case: dict[str, object] = {"id": "run", "source": "agents/c.py:run"}
    case.update(fields)
    return case


def _repo(tmp_path: Path, text: str = CONSUMER) -> Path:
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "c.py").write_text(text)
    return tmp_path


class TestScoreCase:
    def test_found_missed_and_false(self, tmp_path: Path) -> None:
        expected = [{"path": "task"}, {"path": "task.model"}, {"path": "summary"}]
        score = benchmark.score_case(_case(expected=expected), _repo(tmp_path))
        assert score.hits == {"task", "task.model"}
        assert score.missed == {"summary"}
        assert score.false == {"extra"}
        assert score.error is None

    def test_case_without_source_finds_nothing(self, tmp_path: Path) -> None:
        score = benchmark.score_case(_case(source=None, expected=[{"path": "x"}]), tmp_path)
        assert score.missed == {"x"}
        assert score.error == "no consumer function"

    def test_analysis_error_counts_as_missed(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, "def run():\n    return 1\n")
        score = benchmark.score_case(_case(expected=[{"path": "x"}]), repo)
        assert score.missed == {"x"}
        assert score.error is not None
        assert score.error == "Function 'run' in agents/c.py takes no input parameter"

    def test_replace_renders_a_template_copy(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, "from {{pkg}}.x import y\n\n\n" + CONSUMER)
        case = _case(expected=[{"path": "task"}], replace=[["{{pkg}}", "pkg"]])
        assert benchmark.score_case(case, repo).hits == {"task"}
        assert "{{pkg}}" in (repo / "agents" / "c.py").read_text()

    def test_error_on_a_rendered_copy_names_the_repo_file(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, "def run():\n    return '{{pkg}}'\n")
        case = _case(expected=[{"path": "x"}], replace=[["{{pkg}}", "pkg"]])
        error = benchmark.score_case(case, repo).error
        assert error == "Function 'run' in agents/c.py takes no input parameter"


class TestReport:
    def test_dotted_marks_list_items(self) -> None:
        assert benchmark.dotted(("searches", "[]", "query")) == "searches[].query"
        assert benchmark.dotted(("a", "b")) == "a.b"

    def test_field_paths_include_parents(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, "def run(state):\n    return state['a']['b']\n")
        assert benchmark.field_paths(repo / "agents" / "c.py", "run") == {"a", "a.b"}

    def test_totals_and_share(self, tmp_path: Path) -> None:
        expected = [{"path": "task"}, {"path": "summary"}]
        project = benchmark.ProjectScore("p")
        project.cases = [benchmark.score_case(_case(expected=expected), _repo(tmp_path))]
        lines = benchmark.report([project], verbose=True).splitlines()
        assert lines[1].split() == ["p", "1", "2", "2"]
        assert "    missed summary" in lines
        assert "    false  extra" in lines
        assert lines[-1].split() == ["total", "1", "2", "2", "found", "50%"]
