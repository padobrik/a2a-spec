"""Specs that use removed content fail to load with a migration message."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_handshake.exceptions import ConfigError
from agent_handshake.spec.loader import load_spec

BASE = """spec:
  name: t2r
  version: "1.0"
  producer: triage
  consumer: resolution
  structural:
    type: object
"""


def _spec(tmp_path: Path, extra: str) -> Path:
    path = tmp_path / "spec.yaml"
    path.write_text(BASE + extra)
    return path


@pytest.mark.parametrize(
    ("validator", "advice"),
    [
        ("no_pii_in_output", "Use a regex policy rule with your own patterns"),
        ("output_not_empty", "List the fields the consumer needs in structural.required"),
    ],
)
def test_builtin_validator_removed(tmp_path: Path, validator: str, advice: str) -> None:
    path = _spec(
        tmp_path,
        "  policy:\n"
        "    - rule: r\n"
        "      method: custom\n"
        f"      validator: agent_handshake.policy.builtin.{validator}\n",
    )
    with pytest.raises(ConfigError) as info:
        load_spec(path)
    message = str(info.value)
    assert message.startswith(f"{path}: Validator 'agent_handshake.policy.builtin.{validator}'")
    assert "was removed in 0.9." in message
    assert advice in message
    assert message.endswith("See CHANGELOG.md.")


def test_own_custom_validator_still_loads(tmp_path: Path) -> None:
    path = _spec(
        tmp_path, "  policy:\n    - rule: r\n      method: custom\n      validator: checks.mine\n"
    )
    assert load_spec(path).policy[0].validator == "checks.mine"
