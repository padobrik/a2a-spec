"""Run the README story and capture real code, spec and pytest output."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

TRIAGE = """async def triage_agent(data: dict) -> dict:
    text = data["message"].lower()
    category = "billing" if "charge" in text else "general"
    return {"category": category, "priority": "high" if "urgent" in text else "low"}
"""
RESOLUTION = """async def resolution_agent(ticket: dict) -> dict:
    escalate = ticket.get("priority", "low") == "high"
    return {"reply": f"We are checking your {ticket['category']} issue.", "escalate": escalate}
"""
ADAPTERS = """from a2a_spec import FunctionAdapter
from agents.triage import triage_agent

ADAPTERS = {
    "triage-agent": FunctionAdapter(fn=triage_agent, agent_id="triage-agent", version="1.0"),
}
"""
SCENARIOS = """scenarios:
  - name: double_charge
    input:
      message: "I was charged twice. This is urgent."
"""


@dataclass
class Capture:
    consumer_code: list[str]
    spec_lines: list[str]
    pytest_cmd: str
    pytest_lines: list[str]


def capture() -> Capture:
    """Run the README story and keep the real code, spec and pytest output."""
    env = {**os.environ, "NO_COLOR": "1", "COLUMNS": "96"}
    env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env['PATH']}"

    def run(cmd: str, cwd: Path, expect: int = 0) -> str:
        proc = subprocess.run(
            cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True, check=False
        )
        if proc.returncode != expect:
            sys.exit(
                f"'{cmd}' exited {proc.returncode}, expected {expect}:\n{proc.stdout}{proc.stderr}"
            )
        return proc.stdout

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "agents").mkdir()
        (root / "agents" / "triage.py").write_text(TRIAGE)
        (root / "agents" / "resolution.py").write_text(RESOLUTION)
        run("a2aspec init", root)
        (root / "a2a_spec" / "specs" / "example-spec.yaml").unlink()
        (root / "a2a_spec" / "scenarios" / "example-scenarios.yaml").unlink()
        (root / "a2a_spec" / "adapters" / "__init__.py").write_text(ADAPTERS)
        (root / "a2a_spec" / "scenarios" / "support.yaml").write_text(SCENARIOS)
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'a2a_config = "a2a-spec.yaml"\n'
            'testpaths = ["a2a_spec/specs"]\n'
        )
        run("a2aspec record", root)
        run(
            "a2aspec infer --producer triage-agent --consumer resolution-agent "
            "--source agents/resolution.py:resolution_agent",
            root,
        )
        spec = (root / "a2a_spec" / "specs" / "triage-agent-to-resolution-agent.yaml").read_text()
        triage = root / "agents" / "triage.py"
        triage.write_text(triage.read_text().replace('"priority":', '"urgency":'))
        run("a2aspec record", root)
        cmd = "pytest -q --no-header -p no:cacheprovider"
        out = run(cmd, root, expect=1)

    spec_lines = [line for line in spec.splitlines() if not line.startswith("#")][:16]
    keep = ("FAILED", "PASSED", "violated", "required property", "failed", "passed")
    pytest_lines = [line.rstrip() for line in out.splitlines() if any(k in line for k in keep)]
    return Capture(RESOLUTION.splitlines(), spec_lines, f"$ {cmd.split(' -p')[0]}", pytest_lines)
