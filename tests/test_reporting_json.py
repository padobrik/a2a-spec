"""Tests for JSON report generation."""

from __future__ import annotations

import json

from agent_handshake.reporting.json_report import generate_json_report


class TestJsonReport:
    def test_all_passed(self) -> None:
        results = [
            {
                "spec_name": "s1",
                "scenario": "sc1",
                "passed": True,
                "errors": [],
                "duration_ms": 1.234,
            },
            {"spec_name": "s2", "scenario": "sc2", "passed": True, "errors": [], "duration_ms": 2},
        ]
        report = json.loads(generate_json_report(results, project_name="test-project"))
        assert report["project"] == "test-project"
        assert report["summary"] == {"total": 2, "passed": 2, "failed": 0}
        assert [r["spec"] for r in report["results"]] == ["s1", "s2"]
        assert [r["scenario"] for r in report["results"]] == ["sc1", "sc2"]
        assert all(r["passed"] for r in report["results"])
        assert report["results"][0]["duration_ms"] == 1.2

    def test_with_failures(self) -> None:
        results = [
            {"spec_name": "s1", "scenario": "sc1", "passed": True, "errors": []},
            {
                "spec_name": "s2",
                "scenario": "sc2",
                "passed": False,
                "errors": ["Missing field", "Bad type"],
            },
        ]
        report = json.loads(generate_json_report(results, project_name="test-project"))
        assert report["summary"] == {"total": 2, "passed": 1, "failed": 1}
        failed = report["results"][1]
        assert failed["passed"] is False
        assert failed["errors"] == ["Missing field", "Bad type"]

    def test_empty_results(self) -> None:
        report = json.loads(generate_json_report([], project_name="test-project"))
        assert report["summary"] == {"total": 0, "passed": 0, "failed": 0}
        assert report["results"] == []

    def test_output_is_valid_json(self) -> None:
        results = [
            {
                "spec_name": "s1",
                "scenario": "sc1",
                "passed": False,
                "errors": ['structural: [<root>] "category" is required'],
            }
        ]
        # json.loads raises on anything that is not a single JSON document.
        json.loads(generate_json_report(results, project_name="p"))
