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


@pytest.mark.parametrize("method", ["embedding_similarity", "entailment", "language_detection"])
def test_semantic_rule_removed(tmp_path: Path, method: str) -> None:
    path = _spec(tmp_path, f"  semantic:\n    - rule: faithful\n      method: {method}\n")
    with pytest.raises(ConfigError) as info:
        load_spec(path)
    assert str(info.value) == (
        f"{path}: Rule '{method}' was removed in 0.9. "
        "Use a custom validator instead. See CHANGELOG.md."
    )


def test_empty_semantic_section_removed(tmp_path: Path) -> None:
    path = _spec(tmp_path, "  semantic: []\n")
    with pytest.raises(ConfigError, match=r"Section 'semantic' was removed in 0\.9\. Delete it"):
        load_spec(path)


def test_statistical_section_removed(tmp_path: Path) -> None:
    path = _spec(tmp_path, "  statistical:\n    - rule: drift\n      method: ks_test\n")
    with pytest.raises(
        ConfigError, match=r"spec\.yaml: Section 'statistical' was removed in 0\.9\."
    ):
        load_spec(path)


def test_own_custom_validator_still_loads(tmp_path: Path) -> None:
    path = _spec(
        tmp_path, "  policy:\n    - rule: r\n      method: custom\n      validator: checks.mine\n"
    )
    assert load_spec(path).policy[0].validator == "checks.mine"
