"""JSON report generation for machines: CI jobs, agents and scripts.

One JSON object on stdout. Records carry what the JUnit reporter gets, so
both formats describe the same run.
"""

from __future__ import annotations

import json
from typing import Any


def generate_json_report(
    results: list[dict[str, Any]],
    project_name: str,
) -> str:
    """Generate a JSON report from test results.

    Args:
        results: List of test result dicts with keys:
            spec_name, scenario, name, passed, errors, duration_ms
        project_name: Name of the project under test.

    Returns:
        JSON string with a summary and one entry per checked output.
    """
    total = len(results)
    failures = sum(1 for r in results if not r.get("passed", False))

    report = {
        "project": project_name,
        "summary": {
            "total": total,
            "passed": total - failures,
            "failed": failures,
        },
        "results": [
            {
                "spec": r.get("spec_name", "unnamed"),
                "scenario": r.get("scenario", "unnamed"),
                "passed": bool(r.get("passed", False)),
                "errors": list(r.get("errors", [])),
                "duration_ms": round(float(r.get("duration_ms", 0)), 1),
            }
            for r in results
        ],
    }
    return json.dumps(report, ensure_ascii=False, indent=2)
