"""The parameter with the producer's output is chosen by its type; attribute reads count."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_handshake.exceptions import ConfigError
from agent_handshake.infer.consumer import analyze_consumer

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
