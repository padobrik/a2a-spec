"""The parameter with the producer's output is chosen by its type; attribute reads count."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_handshake.exceptions import ConfigError
from agent_handshake.infer.consumer import analyze_consumer

MODELS = """
from dataclasses import dataclass
from typing import NotRequired, TypedDict

from pydantic import BaseModel


class Item(BaseModel):
    query: str
    reason: str


class Plan(BaseModel):
    searches: list[Item]


class Verdict(BaseModel):
    verified: bool
    issues: str = ""


@dataclass
class Detection:
    spam: bool
    email_id: str


class Base(TypedDict):
    title: str


class Layout(Base):
    intro: NotRequired[str]
"""


def _reads(
    tmp_path: Path, body: str, keys: set[str] | None = None
) -> list[tuple[str, tuple[bool, ...]]]:
    (tmp_path / "models.py").write_text(MODELS)
    (tmp_path / "agent.py").write_text(body)
    result = analyze_consumer(tmp_path / "agent.py", "run", keys)
    return [(r.name, r.strict) for r in result.reads]


def _warnings(tmp_path: Path, body: str, keys: set[str] | None = None) -> list[str]:
    (tmp_path / "models.py").write_text(MODELS)
    (tmp_path / "agent.py").write_text(body)
    return analyze_consumer(tmp_path / "agent.py", "run", keys).warnings


HEAD = "from models import Detection, Item, Layout, Plan, Verdict\n\n\n"


class TestParameterChoice:
    def test_typed_parameter_after_a_string(self, tmp_path: Path) -> None:
        body = HEAD + "def run(query: str, v: Verdict):\n    return v.issues\n"
        assert _reads(tmp_path, body) == [("issues", (True,))]

    def test_keys_pick_between_typed_parameters(self, tmp_path: Path) -> None:
        body = HEAD + "def run(self, plan: Plan, v: Verdict):\n    return plan.searches, v.issues\n"
        assert _reads(tmp_path, body, {"verified", "issues"}) == [("issues", (True,))]
        assert _reads(tmp_path, body, {"searches"}) == [("searches", (True,))]

    def test_no_matching_parameter_is_an_error(self, tmp_path: Path) -> None:
        body = HEAD + "def run(item: Item):\n    return item.query\n"
        with pytest.raises(ConfigError, match=r"No parameter of 'run' .*\(item\).*keys: summary"):
            _reads(tmp_path, body, {"summary"})

    def test_type_with_a_minority_of_the_keys_does_not_match(self, tmp_path: Path) -> None:
        body = HEAD + "def run(d: Detection, ctx: Context):\n    return d.email_id\n"
        with pytest.raises(ConfigError, match="No parameter"):
            _reads(tmp_path, body, {"email_id", "email_content"})

    def test_untyped_parameter_is_taken_as_before(self, tmp_path: Path) -> None:
        body = "def run(data, ctx):\n    return data['priority']\n"
        assert _reads(tmp_path, body, {"category"}) == [("priority", (True,))]

    def test_unresolved_type_matches_by_its_reads(self, tmp_path: Path) -> None:
        body = "def run(response: Response, ctx: Context):\n    return response.agent.text\n"
        assert _reads(tmp_path, body, {"agent"}) == [
            ("agent.text", (True, True)),
        ]
        with pytest.raises(ConfigError, match="No parameter"):
            _reads(tmp_path, body, {"email_id"})


class TestAttributeReads:
    def test_attributes_getattr_and_aliases(self, tmp_path: Path) -> None:
        body = HEAD + (
            "def run(d: Detection):\n"
            "    a = getattr(d, 'email_id', '')\n"
            "    b = getattr(d, 'spam')\n"
            "    return d.spam, a, b\n"
        )
        assert _reads(tmp_path, body) == [
            ("email_id", (False,)),
            ("spam", (True,)),
            ("spam", (True,)),
        ]

    def test_method_of_the_input_is_not_a_field(self, tmp_path: Path) -> None:
        body = HEAD + "def run(v: Verdict):\n    return v.model_dump()\n"
        assert _reads(tmp_path, body) == []
        assert "'v' calls .model_dump()" in _warnings(tmp_path, body)[0]

    def test_list_of_outputs(self, tmp_path: Path) -> None:
        body = HEAD + (
            "from collections.abc import Sequence\n\n"
            "def run(query: str, verdicts: Sequence[Verdict]):\n"
            "    return [v.issues for v in verdicts], verdicts[0].verified\n"
        )
        assert _reads(tmp_path, body) == [("issues", (True,)), ("verified", (True,))]

    def test_framework_result(self, tmp_path: Path) -> None:
        body = (
            "def run(result: RunResult | RunResultStreaming):\n"
            "    a = result.final_output.summary\n"
            "    b = result.final_output_as(Summary).title\n"
            "    return a, b, result.new_items\n"
        )
        assert _reads(tmp_path, body) == [("summary", (True,)), ("title", (True,))]


class TestTypes:
    def test_type_from_a_relative_import_and_inheritance(self, tmp_path: Path) -> None:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "models.py").write_text(MODELS)
        (pkg / "agent.py").write_text(
            "from .models import Layout\n\n\ndef run(q: str, layout: Layout):\n"
            "    return layout['title'], layout.get('intro'), layout['extra']\n"
        )
        result = analyze_consumer(pkg / "agent.py", "run", {"title", "intro"})
        assert [r.name for r in result.reads] == ["title", "intro", "extra"]
        assert result.warnings == [
            "line 5: 'extra' is not a field of Layout; the inferred contract may be incomplete"
        ]

    def test_undeclared_attribute_warns(self, tmp_path: Path) -> None:
        body = HEAD + "def run(v: Verdict):\n    return v.verified, v.score\n"
        assert _warnings(tmp_path, body) == [
            "line 5: 'score' is not a field of Verdict; the inferred contract may be incomplete"
        ]


SCHEMAS = """
import { z } from 'zod';

export const Verdict = z.object({ verified: z.boolean(), issues: z.string().optional() });
export type Verdict = z.infer<typeof Verdict>;

export const Report = z.object({ summary: z.string(), body: z.string() });
export type Report = z.infer<typeof Report>;

export interface Detection { spam: boolean; emailId?: string }
"""


def _ts(tmp_path: Path, body: str, keys: set[str] | None = None):
    pytest.importorskip("tree_sitter_typescript", reason="needs the typescript extra")
    (tmp_path / "agents.ts").write_text(SCHEMAS)
    (tmp_path / "manager.ts").write_text(
        "import { Verdict, Report, Detection } from './agents.ts';\n\n" + body
    )
    return analyze_consumer(tmp_path / "manager.ts", "run", keys)


class TestTypeScript:
    def test_zod_types_pick_the_parameter(self, tmp_path: Path) -> None:
        body = (
            "function run(query: string, report: Report, verdict: Verdict) {\n"
            "  return report.summary + verdict.issues;\n}\n"
        )
        result = _ts(tmp_path, body, {"verified", "issues"})
        assert [r.name for r in result.reads] == ["issues"]
        assert [r.name for r in _ts(tmp_path, body, {"summary", "body"}).reads] == ["summary"]

    def test_interface_and_undeclared_field(self, tmp_path: Path) -> None:
        body = "function run(q: string, d: Detection) {\n  return d.spam && d.score;\n}\n"
        result = _ts(tmp_path, body)
        assert [r.name for r in result.reads] == ["spam", "score"]
        assert result.warnings == [
            "line 4: 'score' is not a field of Detection; the inferred contract may be incomplete"
        ]

    def test_list_of_outputs(self, tmp_path: Path) -> None:
        body = (
            "function run(q: string, verdicts: Verdict[]) {\n"
            "  for (const v of verdicts) { v.verified; }\n"
            "  return verdicts.map(v => v.issues).concat(verdicts[0].issues);\n}\n"
        )
        assert sorted({r.name for r in _ts(tmp_path, body).reads}) == ["issues", "verified"]

    def test_framework_result(self, tmp_path: Path) -> None:
        body = (
            "function run(runResult: RunResult<unknown, any>) {\n"
            "  return String(runResult.finalOutput.summary) + runResult.state;\n}\n"
        )
        assert [r.name for r in _ts(tmp_path, body, {"summary"}).reads] == ["summary"]

    def test_no_matching_parameter_is_an_error(self, tmp_path: Path) -> None:
        body = "function run(d: Detection) {\n  return d.spam;\n}\n"
        with pytest.raises(ConfigError, match=r"No parameter of 'run' .*\(d\)"):
            _ts(tmp_path, body, {"summary"})
