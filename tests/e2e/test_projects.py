"""End-to-end scenarios: real projects driven through the installed ``handshake`` command.

Each directory in ``projects/`` is a small project with a ``scenario.yaml``:

    description: what the scenario shows
    requires: [tree_sitter_typescript]   # optional: modules that must import
    steps:
      - run: handshake test
        exit: 1
        output: ["'priority' is a required property"]   # all must appear
        not_output: ["Traceback"]                        # none may appear
        files: {handshake/specs/x.yaml: ["required:"]}  # file must contain
      - copy: {changed/triage.py: agents/triage.py}     # replace a file, no command

The project is copied to a temporary directory and every step runs there in
a subprocess. ``handshake`` is the console script next to the running Python,
or ``$HANDSHAKE_BIN``, so CI can point the scenarios at an installed wheel.
``pytest`` runs with the same Python; ``git`` runs as is.
"""

from __future__ import annotations

import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

PROJECTS = Path(__file__).parent / "projects"
STEP_TIMEOUT = 180  # seconds; a hung command fails the scenario instead of blocking CI
SCENARIOS = sorted(p.parent for p in PROJECTS.glob("*/scenario.yaml"))


def _handshake() -> str:
    explicit = os.environ.get("HANDSHAKE_BIN")
    if explicit:
        return explicit
    scripts = Path(sys.executable).parent
    for name in ("handshake", "handshake.exe"):
        if (scripts / name).exists():
            return str(scripts / name)
    found = shutil.which("handshake")
    if found is None:
        pytest.skip("the handshake command is not installed")
    return found


def _command(line: str) -> list[str]:
    args = shlex.split(line)
    if args[0] == "handshake":
        return [_handshake(), *args[1:]]
    if args[0] == "pytest":
        return [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args[1:]]
    if args[0] == "git":
        return args
    raise ValueError(f"unsupported command in scenario: {line}")


def _environment(workdir: Path) -> dict[str, str]:
    # No API keys, and no GIT_* variables: GIT_DIR or GIT_WORK_TREE from a
    # git hook would point the scenario's git commands at another repository.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.endswith("_API_KEY") and not k.startswith("GIT_")
    }
    env.pop("GITHUB_WORKSPACE", None)  # annotation paths stay absolute
    env.update(
        {
            "COLUMNS": "200",  # keep rich from wrapping lines the scenarios match
            "NO_COLOR": "1",
            "PYTHONIOENCODING": "utf-8",
            "GIT_AUTHOR_NAME": "e2e",
            "GIT_AUTHOR_EMAIL": "e2e@example.com",
            "GIT_COMMITTER_NAME": "e2e",
            "GIT_COMMITTER_EMAIL": "e2e@example.com",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return env


@pytest.mark.parametrize("project", SCENARIOS, ids=[p.name for p in SCENARIOS])
def test_scenario(project: Path, tmp_path: Path) -> None:
    scenario: dict[str, Any] = yaml.safe_load((project / "scenario.yaml").read_text("utf-8"))
    for module in scenario.get("requires", []):
        if importlib.util.find_spec(module) is None:
            pytest.skip(f"needs {module}")

    workdir = tmp_path / project.name
    shutil.copytree(project, workdir, ignore=shutil.ignore_patterns("scenario.yaml"))
    env = _environment(workdir)

    for number, step in enumerate(scenario["steps"], start=1):
        if "copy" in step:
            for source, target in step["copy"].items():
                shutil.copyfile(workdir / source, workdir / target)
            continue
        where = f"step {number} `{step['run']}`"
        try:
            proc = subprocess.run(
                _command(step["run"]),
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=STEP_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(f"{where} did not finish in {STEP_TIMEOUT}s")
        output = proc.stdout + proc.stderr
        expected_exit = step.get("exit", 0)
        assert proc.returncode == expected_exit, (
            f"{where} exited {proc.returncode}, expected {expected_exit}:\n{output}"
        )
        for text in step.get("output", []):
            assert text in output, f"{where}: missing {text!r} in:\n{output}"
        for text in step.get("not_output", []):
            assert text not in output, f"{where}: unexpected {text!r} in:\n{output}"
        for name, texts in step.get("files", {}).items():
            content = (workdir / name).read_text("utf-8")
            for text in texts:
                assert text in content, f"{where}: {name} lacks {text!r}:\n{content}"
