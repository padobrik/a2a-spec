"""Example pytest integration for agent-handshake.

This demonstrates how to use agent-handshake in your existing pytest suite.
"""

from __future__ import annotations

from pathlib import Path

from agent_handshake.spec.loader import load_spec
from agent_handshake.spec.validator import validate_output
from agent_handshake.snapshot.store import SnapshotStore
from agent_handshake.snapshot.replay import ReplayEngine
from agent_handshake.policy.engine import PolicyEngine

EXAMPLE_DIR = Path(__file__).parent.parent / "handshake"
SPEC_PATH = EXAMPLE_DIR / "specs" / "triage-to-resolution.yaml"
SNAPSHOTS_DIR = EXAMPLE_DIR / "snapshots"


def test_triage_output_matches_spec() -> None:
    """Validate that the triage agent snapshot matches the spec."""
    spec = load_spec(SPEC_PATH)

    store = SnapshotStore(SNAPSHOTS_DIR)
    engine = ReplayEngine(store)

    output = engine.replay("triage-agent", "billing_overcharge")

    result = validate_output(output, spec)
    assert result.passed, f"Validation failed: {result.errors}"


def test_triage_output_no_internal_ids() -> None:
    """Validate that triage output leaks no internal ticket IDs."""
    spec = load_spec(SPEC_PATH)

    store = SnapshotStore(SNAPSHOTS_DIR)
    engine = ReplayEngine(store)
    output = engine.replay("triage-agent", "billing_overcharge")

    policy_engine = PolicyEngine()
    results = policy_engine.evaluate(output, {}, spec.policy)
    for r in results:
        assert r.passed, f"Policy '{r.rule_name}' failed: {r.detail}"


def test_triage_output_has_billing_category() -> None:
    """Verify the triage agent correctly classifies billing issues."""
    store = SnapshotStore(SNAPSHOTS_DIR)
    engine = ReplayEngine(store)
    output = engine.replay("triage-agent", "billing_overcharge")

    assert output["category"] == "billing"
    assert output["confidence"] > 0.8
