"""JUnit XML report generation for CI systems."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any


def generate_junit_xml(
    results: list[dict[str, Any]],
    suite_name: str = "a2a-spec",
) -> str:
    """Generate JUnit XML from test results.

    Args:
        results: List of test result dicts with keys:
            name, passed, errors, duration_ms
        suite_name: Name for the test suite.

    Returns:
        XML string.
    """
    total = len(results)
    failures = sum(1 for r in results if not r.get("passed", False))

    suite = ET.Element(
        "testsuite",
        {
            "name": suite_name,
            "tests": str(total),
            "failures": str(failures),
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    for r in results:
        tc = ET.SubElement(
            suite,
            "testcase",
            {
                "name": r.get("name", "unnamed"),
                "classname": r.get("spec_name", "a2a-spec"),
                "time": str(r.get("duration_ms", 0) / 1000),
            },
        )

        if not r.get("passed", False):
            ET.SubElement(
                tc,
                "failure",
                {
                    "message": "; ".join(r.get("errors", ["Unknown error"])),
                },
            )

    return ET.tostring(suite, encoding="unicode", xml_declaration=True)
