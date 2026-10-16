"""Tests for CLI diff command."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from agent_handshake.cli.main import app

runner = CliRunner()


class TestCliDiff:
    def test_diff_help(self) -> None:
        result = runner.invoke(app, ["diff", "--help"])
        assert result.exit_code == 0
        # Rich adds colour codes on CI runners; compare the plain text.
        assert "--base" in re.sub(r"\x1b\[[0-9;]*m", "", result.output)

    def test_diff_no_snapshots(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "handshake.yaml"
        config.write_text(
            f'project_name: test\nstorage:\n  path: "{(tmp_path / "empty_snaps").as_posix()}"'
        )
        result = runner.invoke(app, ["diff", "--config", str(config)])
        assert result.exit_code == 0

    def test_diff_invalid_config(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "bad.yaml"
        config.write_text("- not a mapping")
        result = runner.invoke(app, ["diff", "--config", str(config)])
        assert result.exit_code != 0


def _git(repo, *args: str) -> None:
    import subprocess

    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _write_snapshot(repo, scenario: str, output: dict) -> None:
    import json

    agent_dir = repo / "snapshots" / "triage-agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / f"{scenario}_abc123.json").write_text(
        json.dumps(
            {
                "fingerprint": "abc123",
                "agent_id": "triage-agent",
                "scenario": scenario,
                "input": {"message": "hi"},
                "output": output,
            }
        )
    )


def _isolate_git(monkeypatch) -> None:
    """Keep the developer's global git config and hooks out of test repos."""
    import os

    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _repo(tmp_path, monkeypatch):
    _isolate_git(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "handshake.yaml").write_text("storage:\n  path: snapshots\n")
    _git(tmp_path, "init", "-q")
    _write_snapshot(tmp_path, "billing", {"category": "billing", "summary": "duplicate charge"})
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "baseline")
    return tmp_path


def _flat(text: str) -> str:
    return " ".join(text.split())


class TestCliDiffGitBaseline:
    def test_rerecorded_change_is_reported(self, tmp_path, monkeypatch) -> None:
        repo = _repo(tmp_path, monkeypatch)
        _write_snapshot(repo, "billing", {"summary": "duplicate charge"})
        result = runner.invoke(app, ["diff"])
        assert result.exit_code == 2, result.output
        assert "triage-agent / billing" in result.output
        assert "category" in result.output
        assert "No differences detected" not in result.output

    def test_unchanged_reports_nothing(self, tmp_path, monkeypatch) -> None:
        _repo(tmp_path, monkeypatch)
        result = runner.invoke(app, ["diff"])
        assert result.exit_code == 0, result.output
        assert "No differences detected" in result.output
        assert "[diff] Diff Report" in result.output

    def test_new_scenario(self, tmp_path, monkeypatch) -> None:
        repo = _repo(tmp_path, monkeypatch)
        _write_snapshot(repo, "shipping", {"category": "shipping"})
        result = runner.invoke(app, ["diff"])
        assert result.exit_code == 0, result.output
        assert "NEW triage-agent / shipping: not in HEAD" in _flat(result.output)

    def test_deleted_snapshot_fails(self, tmp_path, monkeypatch) -> None:
        repo = _repo(tmp_path, monkeypatch)
        (repo / "snapshots" / "triage-agent" / "billing_abc123.json").unlink()
        _write_snapshot(repo, "shipping", {"category": "shipping"})
        result = runner.invoke(app, ["diff"])
        assert result.exit_code == 2, result.output
        assert "GONE triage-agent / billing_abc123.json: deleted since HEAD" in _flat(result.output)

    def test_base_revision(self, tmp_path, monkeypatch) -> None:
        repo = _repo(tmp_path, monkeypatch)
        _write_snapshot(repo, "billing", {"category": "shipping", "summary": "duplicate charge"})
        _git(repo, "commit", "-q", "-am", "second")
        assert runner.invoke(app, ["diff"]).exit_code == 0
        result = runner.invoke(app, ["diff", "--base", "HEAD~1"])
        assert "triage-agent / billing" in result.output
        assert "category" in result.output

    def test_unknown_revision(self, tmp_path, monkeypatch) -> None:
        _repo(tmp_path, monkeypatch)
        result = runner.invoke(app, ["diff", "--base", "nope"])
        assert result.exit_code == 1
        assert "Unknown git revision 'nope'" in _flat(result.output)

    def test_not_a_git_repo(self, tmp_path, monkeypatch) -> None:
        _isolate_git(monkeypatch)
        monkeypatch.chdir(tmp_path)
        (tmp_path / "handshake.yaml").write_text("storage:\n  path: snapshots\n")
        _write_snapshot(tmp_path, "billing", {"category": "billing"})
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
        result = runner.invoke(app, ["diff"])
        assert result.exit_code == 1
        assert "not in a git repository" in _flat(result.output)

    def test_added_field_does_not_fail(self, tmp_path, monkeypatch) -> None:
        repo = _repo(tmp_path, monkeypatch)
        _write_snapshot(
            repo,
            "billing",
            {"category": "billing", "summary": "duplicate charge", "confidence": 0.9},
        )
        result = runner.invoke(app, ["diff"])
        assert result.exit_code == 0, result.output
        assert "LOW" in result.output
        assert "confidence" in result.output
