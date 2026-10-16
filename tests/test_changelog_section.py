"""Tests for the script that takes release notes from CHANGELOG.md."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import agent_handshake

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "changelog_section.py"
_spec = importlib.util.spec_from_file_location("changelog_section", SCRIPT)
assert _spec is not None and _spec.loader is not None
changelog_section = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(changelog_section)

TEXT = """# Changelog

## [Unreleased]

## [0.2.0] - 2026-10-16

### Added
- Streaming.

## [0.1.0] - 2026-10-01

### Added
- First release.

[0.2.0]: https://example.com/v0.2.0
[0.1.0]: https://example.com/v0.1.0
"""


class TestSection:
    def test_middle_section(self) -> None:
        assert changelog_section.section(TEXT, "0.2.0") == "### Added\n- Streaming."

    def test_last_section_drops_link_definitions(self) -> None:
        assert changelog_section.section(TEXT, "0.1.0") == "### Added\n- First release."

    def test_missing_version(self) -> None:
        assert changelog_section.section(TEXT, "0.3.0") is None

    def test_empty_section(self) -> None:
        assert changelog_section.section(TEXT, "Unreleased") is None

    def test_version_is_not_a_pattern(self) -> None:
        assert changelog_section.section(TEXT.replace("0.2.0", "0x2y0"), "0.2.0") is None


class TestScript:
    def test_current_version_has_notes(self) -> None:
        """A version bump without CHANGELOG notes fails here, before any release."""
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), f"v{agent_handshake.__version__}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip()

    def test_unknown_version_fails(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "99.0.0"], capture_output=True, text=True, check=False
        )
        assert proc.returncode == 1
        assert "no notes for 99.0.0" in proc.stderr
