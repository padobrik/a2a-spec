"""Tests for JUnit XML report generation."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from agent_handshake.reporting.junit import generate_junit_xml


def test_counts_and_failure_messages() -> None:
    xml = generate_junit_xml(
        [
            {"name": "ok", "spec_name": "s", "passed": True, "duration_ms": 1500},
            {"name": "bad", "passed": False, "errors": ["missing a", "wrong b"]},
        ]
    )
    suite = ET.fromstring(xml)
    assert (suite.get("name"), suite.get("tests"), suite.get("failures")) == (
        "agent-handshake",
        "2",
        "1",
    )
    ok, bad = suite.findall("testcase")
    assert (ok.get("classname"), ok.get("time"), ok.find("failure")) == ("s", "1.5", None)
    failure = bad.find("failure")
    assert failure is not None
    assert failure.get("message") == "missing a; wrong b"


def test_failure_without_errors() -> None:
    suite = ET.fromstring(generate_junit_xml([{"passed": False}], suite_name="x"))
    case = suite.find("testcase")
    assert case is not None
    assert case.get("name") == "unnamed"
    failure = case.find("failure")
    assert failure is not None
    assert failure.get("message") == "Unknown error"
