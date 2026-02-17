"""Tests for markdown report generation."""

from __future__ import annotations

from a2a_spec.reporting.markdown import generate_report


class TestMarkdownReport:
    def test_all_passed(self) -> None:
        results = [
            {"spec_name": "s1", "scenario": "sc1", "passed": True},
            {"spec_name": "s2", "scenario": "sc2", "passed": True},
        ]
        report = generate_report("test-project", results)
        assert "# a2a-spec Report: test-project" in report
        assert "2/2 passed" in report
        assert "Failures" not in report

    def test_with_failures(self) -> None:
        results = [
            {"spec_name": "s1", "scenario": "sc1", "passed": True},
            {"spec_name": "s2", "scenario": "sc2", "passed": False, "errors": ["Missing field"]},
        ]
        report = generate_report("test-project", results)
        assert "1/2 passed" in report
        assert "Failures" in report
        assert "Missing field" in report

    def test_with_diff_results(self) -> None:
        results = [{"spec_name": "s1", "scenario": "sc1", "passed": True}]
        diffs = [{"field": "summary", "severity": "high", "explanation": "Semantic drift"}]
        report = generate_report("test-project", results, diff_results=diffs)
        assert "Semantic Drift" in report
        assert "summary" in report

    def test_empty_results(self) -> None:
        report = generate_report("test-project", [])
        assert "0/0 passed" in report

    def test_footer_present(self) -> None:
        report = generate_report("test-project", [])
        assert "a2a-spec" in report
        assert "---" in report

    def test_multiple_errors(self) -> None:
        results = [
            {
                "spec_name": "spec-a",
                "scenario": "test1",
                "passed": False,
                "errors": ["Error 1", "Error 2", "Error 3"],
            },
        ]
        report = generate_report("proj", results)
        assert "Error 1" in report
        assert "Error 2" in report
        assert "Error 3" in report
