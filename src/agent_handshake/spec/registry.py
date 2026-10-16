"""Discover and index specs for a project."""

from __future__ import annotations

from pathlib import Path

from a2a_spec.spec.loader import load_all_specs
from a2a_spec.spec.schema import Spec


class SpecRegistry:
    """Registry of all specs in a project.

    Provides lookup by producer, consumer, or name.
    """

    def __init__(self, specs: list[Spec] | None = None) -> None:
        self._specs: dict[str, Spec] = {}
        if specs:
            for spec in specs:
                self.register(spec)

    def register(self, spec: Spec) -> None:
        """Register a spec."""
        self._specs[spec.name] = spec

    def get(self, name: str) -> Spec | None:
        """Get a spec by name."""
        return self._specs.get(name)

    def get_by_producer(self, producer: str) -> list[Spec]:
        """Get all specs where a given agent is the producer."""
        return [s for s in self._specs.values() if s.producer == producer]

    def get_by_consumer(self, consumer: str) -> list[Spec]:
        """Get all specs where a given agent is the consumer."""
        return [s for s in self._specs.values() if s.consumer == consumer]

    def all(self) -> list[Spec]:
        """Get all registered specs."""
        return list(self._specs.values())

    @classmethod
    def from_directory(cls, directory: str | Path) -> SpecRegistry:
        """Build a registry from a directory of spec YAML files."""
        specs = load_all_specs(directory)
        return cls(specs)

    def __len__(self) -> int:
        return len(self._specs)
