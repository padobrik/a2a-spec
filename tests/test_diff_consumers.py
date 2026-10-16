"""diff rated by what consumers read: FAIL for fields a spec names, INFO for others."""

from __future__ import annotations

from typing import Any

from agent_handshake.diff.consumers import rate_for_consumers
from agent_handshake.diff.engine import DiffEngine, DriftSeverity
from agent_handshake.spec.schema import Spec, StructuralSpec


def _spec(
    name: str = "t2r",
    consumer: str = "resolution",
    properties: dict[str, Any] | None = None,
    inferred: bool = True,
) -> Spec:
    return Spec(
        name=name,
        version="1.0",
        producer="triage",
        consumer=consumer,
        inferred_from="agents/resolution.py:resolve" if inferred else None,
        read_at={"priority": [4], "customer.tier": [7, 9]} if inferred else {},
        structural=StructuralSpec(
            required=["priority"],
            properties=properties
            or {
                "priority": {"type": "string"},
                "customer": {"type": "object", "properties": {"tier": {"type": "string"}}},
            },
        ),
    )


OLD = {"priority": "high", "customer": {"tier": "pro"}, "summary": "s", "category": "billing"}


def _rate(new: dict[str, Any], specs: list[Spec]) -> dict[str, tuple[DriftSeverity, str]]:
    results = rate_for_consumers(DiffEngine().diff(OLD, new), specs)
    return {r.field: (r.severity, r.explanation) for r in results}


class TestRateForConsumers:
    def test_removed_field_names_reader_and_line(self) -> None:
        rated = _rate({k: v for k, v in OLD.items() if k != "priority"}, [_spec()])
        severity, explanation = rated["priority"]
        assert severity == DriftSeverity.HIGH
        assert explanation == (
            "Field 'priority' was removed; resolution reads it at agents/resolution.py:4"
        )

    def test_type_change_of_a_read_field_fails(self) -> None:
        rated = _rate({**OLD, "priority": 3}, [_spec()])
        assert rated["priority"][0] == DriftSeverity.HIGH

    def test_removed_parent_of_a_read_field_fails_with_all_lines(self) -> None:
        rated = _rate({k: v for k, v in OLD.items() if k != "customer"}, [_spec()])
        severity, explanation = rated["customer"]
        assert severity == DriftSeverity.HIGH
        assert explanation.endswith(
            "resolution reads it at agents/resolution.py:7, agents/resolution.py:9"
        )

    def test_fields_outside_the_spec_are_info(self) -> None:
        new = {k: v for k, v in OLD.items() if k != "summary"} | {"urgency": "high"}
        rated = _rate(new, [_spec()])
        assert rated["summary"] == (
            DriftSeverity.INFO,
            "Field 'summary' was removed; no consumer spec reads it",
        )
        assert rated["urgency"][0] == DriftSeverity.INFO

    def test_value_change_of_a_read_field_keeps_its_rating(self) -> None:
        rated = _rate({**OLD, "priority": "low"}, [_spec()])
        assert rated["priority"][0] == DriftSeverity.MEDIUM

    def test_hand_written_spec_is_named(self) -> None:
        rated = _rate({k: v for k, v in OLD.items() if k != "priority"}, [_spec(inferred=False)])
        assert rated["priority"][1].endswith("spec 't2r' for resolution names it")

    def test_every_consumer_is_listed(self) -> None:
        specs = [_spec(), _spec(name="t2b", consumer="billing", inferred=False)]
        rated = _rate({k: v for k, v in OLD.items() if k != "priority"}, specs)
        assert rated["priority"][1] == (
            "Field 'priority' was removed; resolution reads it at agents/resolution.py:4; "
            "spec 't2b' for billing names it"
        )

    def test_no_specs_keeps_structural_rating(self) -> None:
        rated = _rate({k: v for k, v in OLD.items() if k != "summary"}, [])
        assert rated["summary"][0] == DriftSeverity.HIGH
