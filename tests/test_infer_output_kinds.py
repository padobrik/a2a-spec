"""A producer whose output is text or a list: no fields from another parameter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_handshake.cli.main import app
from agent_handshake.exceptions import ConfigError
from agent_handshake.infer.consumer import analyze_consumer

runner = CliRunner()


def _analyze(tmp_path: Path, code: str, output: str | None, suffix: str = ".py"):
    path = tmp_path / f"agent{suffix}"
    path.write_text(code)
    return analyze_consumer(path, "run", None, output)


class TestListOutput:
    def test_framework_context_read_as_an_object_is_refused(self, tmp_path: Path) -> None:
        code = "async def run(ctx: RunContext[Deps]):\n    return ctx.deps.page, ctx.usage\n"
        with pytest.raises(ConfigError, match=r"\(ctx\) holds the producer's output: .* a list"):
            _analyze(tmp_path, code, "list")

    def test_list_parameter_is_read_per_item(self, tmp_path: Path) -> None:
        code = (
            "from pydantic import BaseModel\n\n\n"
            "class Flight(BaseModel):\n    origin: str\n\n\n"
            "def run(ctx: Context, flights: list[Flight]):\n"
            "    return [f.origin for f in flights], ctx.usage\n"
        )
        assert [r.name for r in _analyze(tmp_path, code, "list").reads] == ["origin"]


class TestTextOutput:
    def test_callback_context_read_as_an_object_is_refused(self, tmp_path: Path) -> None:
        code = (
            "def run(callback_context: CallbackContext):\n    return callback_context.state['x']\n"
        )
        with pytest.raises(ConfigError, match="its output is text"):
            _analyze(tmp_path, code, "text")

    def test_substring_test_on_text_is_not_a_key(self, tmp_path: Path) -> None:
        code = "def run(text, model):\n    return 'I am done' in text, model.name\n"
        result = _analyze(tmp_path, code, "text")
        assert result.param == "text"
        assert result.reads == []

    def test_substring_test_on_a_str_parameter_is_not_a_key(self, tmp_path: Path) -> None:
        code = "def run(note: str):\n    return 'urgent' in note\n"
        assert _analyze(tmp_path, code, None).reads == []

    def test_typescript_object_reads_are_refused(self, tmp_path: Path) -> None:
        pytest.importorskip("tree_sitter_typescript", reason="needs the typescript extra")
        code = "function run(ctx) {\n  return ctx.state.report;\n}\n"
        with pytest.raises(ConfigError, match="its output is text"):
            _analyze(tmp_path, code, "text", suffix=".ts")


def test_infer_refuses_a_parameter_that_cannot_hold_text(tmp_path: Path) -> None:
    snaps = tmp_path / "snapshots" / "composer"
    snaps.mkdir(parents=True)
    snapshot = {"schema_version": 1, "agent_id": "composer", "scenario": "s", "input": {}}
    (snaps / "s_1.json").write_text(json.dumps({**snapshot, "output": "A report."}))
    (tmp_path / "consumer.py").write_text(
        "def run(ctx: CallbackContext):\n    return ctx.state['sources']\n"
    )
    config = tmp_path / "handshake.yaml"
    config.write_text(
        f'project_name: t\nspecs_dir: "{(tmp_path / "specs").as_posix()}"\n'
        f'storage:\n  path: "{(tmp_path / "snapshots").as_posix()}"\n'
    )
    args = ["infer", "--config", str(config), "--producer", "composer", "--consumer", "c"]
    result = runner.invoke(app, [*args, "--source", f"{tmp_path / 'consumer.py'}:run"])
    assert result.exit_code == 2
    assert "its output is text" in " ".join(result.output.split())
    assert not (tmp_path / "specs").exists()
