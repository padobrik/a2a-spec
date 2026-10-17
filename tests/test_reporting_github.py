"""Tests for GitHub Actions annotations."""

from __future__ import annotations

import pytest

from agent_handshake.reporting.github import format_github_annotation, print_annotations


def test_format_escapes_properties_and_message() -> None:
    line = format_github_annotation(
        file="a:b,c.md", line=3, level="error", message="50% off\nnext", title="t,1"
    )
    assert line == "::error file=a%3Ab%2Cc.md,line=3,title=t%2C1::50%25 off%0Anext"


def test_print_writes_one_line_each(capsys: pytest.CaptureFixture[str]) -> None:
    print_annotations(["::error::one", "::warning::two"])
    assert capsys.readouterr().out == "::error::one\n::warning::two\n"
