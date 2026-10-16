"""Tests for the bundled agent skill and the skill command."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import typer.main
import yaml
from typer.testing import CliRunner

from agent_handshake.cli.main import app
from agent_handshake.cli.skill_cmd import skill_text

pytest_plugins = ["pytester"]

runner = CliRunner()
FLAG = re.compile(r"--[a-z][a-z0-9-]*")


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    data = yaml.safe_load(match.group(1))
    assert isinstance(data, dict)
    return data


def _cli_options() -> dict[str, set[str]]:
    # Duck-typed: recent typer versions no longer subclass click's classes.
    group = typer.main.get_command(app)
    options: dict[str, set[str]] = {}
    for name, command in group.commands.items():  # type: ignore[attr-defined]
        flags: set[str] = set()
        for param in command.params:
            if param.param_type_name == "option":
                flags.update(o for o in param.opts + param.secondary_opts if o.startswith("--"))
        options[name] = flags
    assert "test" in options and "--no-semantic" in options["test"]
    return options


def _skill_commands(text: str) -> list[tuple[str, list[str]]]:
    """Each `handshake CMD ...` usage in the skill with the flags on that line."""
    joined = text.replace("\\\n", " ")
    return [
        (m.group(1), FLAG.findall(m.group(2)))
        for m in re.finditer(r"(?<![\w-])handshake ([a-z]+)([^`\n]*)", joined)
    ]


class TestSkillContent:
    def test_frontmatter(self) -> None:
        meta = _frontmatter(skill_text())
        assert meta["name"] == "agent-handshake"
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", meta["name"])
        assert 0 < len(meta["description"]) <= 1024

    def test_commands_and_flags_exist(self) -> None:
        options = _cli_options()
        usages = _skill_commands(skill_text())
        assert usages, "skill mentions no handshake commands"
        for command, flags in usages:
            assert command in options, f"skill uses unknown command 'handshake {command}'"
            unknown = set(flags) - options[command]
            assert not unknown, f"'handshake {command}' has no option(s) {sorted(unknown)}"

    def test_every_flag_is_real(self, pytester: pytest.Pytester) -> None:
        known = set().union(*_cli_options().values())
        help_text = pytester.runpytest("--help").stdout.str()
        known |= set(FLAG.findall(help_text))
        unknown = set(FLAG.findall(skill_text())) - known
        assert not unknown, f"skill mentions flags that do not exist: {sorted(unknown)}"


class TestSkillCommand:
    def test_prints_skill(self) -> None:
        result = runner.invoke(app, ["skill"])
        assert result.exit_code == 0
        assert result.stdout == skill_text()

    def test_installs_into_dir(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["skill", "--dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "agent-handshake" / "SKILL.md").read_text(
            encoding="utf-8"
        ) == skill_text()

    def test_refuses_overwrite_without_force(self, tmp_path: Path) -> None:
        target = tmp_path / "agent-handshake" / "SKILL.md"
        target.parent.mkdir()
        target.write_text("custom")
        result = runner.invoke(app, ["skill", "--dir", str(tmp_path)])
        assert result.exit_code == 1
        assert target.read_text() == "custom"
        result = runner.invoke(app, ["skill", "--dir", str(tmp_path), "--force"])
        assert result.exit_code == 0
        assert target.read_text(encoding="utf-8") == skill_text()
