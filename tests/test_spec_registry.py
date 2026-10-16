"""Tests for the spec registry."""

from __future__ import annotations

from pathlib import Path

from agent_handshake.spec.registry import SpecRegistry
from agent_handshake.spec.schema import Spec, StructuralSpec


def _spec(name: str, producer: str, consumer: str) -> Spec:
    return Spec(
        name=name,
        version="1.0",
        producer=producer,
        consumer=consumer,
        structural=StructuralSpec(),
    )


SPECS = [
    _spec("t2r", "triage", "resolution"),
    _spec("t2b", "triage", "billing"),
    _spec("r2b", "resolution", "billing"),
]


class TestSpecRegistry:
    def test_lookup_by_name_producer_and_consumer(self) -> None:
        registry = SpecRegistry(SPECS)
        assert len(registry) == 3
        assert registry.get("t2b") is SPECS[1]
        assert registry.get("missing") is None
        assert [s.name for s in registry.get_by_producer("triage")] == ["t2r", "t2b"]
        assert [s.name for s in registry.get_by_consumer("billing")] == ["t2b", "r2b"]
        assert registry.all() == SPECS

    def test_register_replaces_a_spec_with_the_same_name(self) -> None:
        registry = SpecRegistry()
        registry.register(SPECS[0])
        registry.register(_spec("t2r", "triage", "billing"))
        assert len(registry) == 1
        assert registry.get_by_consumer("resolution") == []

    def test_from_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text(
            "spec:\n  name: t2r\n  version: '1.0'\n  producer: triage\n"
            "  consumer: resolution\n  structural: {}\n"
        )
        registry = SpecRegistry.from_directory(tmp_path)
        assert [s.name for s in registry.all()] == ["t2r"]
