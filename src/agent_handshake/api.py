"""The core API: load recorded snapshots and check them against a spec.

The CLI and the pytest plugin are built on these two functions; integrations
use them the same way.

    from agent_handshake import check, load_snapshots, load_spec

    spec = load_spec("handshake/specs/triage-to-resolution.yaml")
    result = check(spec, load_snapshots("handshake/snapshots"))
    for case in result.failed:
        print(case.snapshot.scenario, case.failures)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_handshake.exceptions import ConfigError
from agent_handshake.policy.engine import PolicyEngine
from agent_handshake.snapshot.store import Snapshot, read_snapshot
from agent_handshake.spec.checker import SpecCheck, SpecChecker
from agent_handshake.spec.schema import Spec


def load_snapshots(source: str | Path) -> list[Snapshot]:
    """Load snapshots from a file, an agent directory or a snapshots directory.

    A directory is searched recursively for ``*.json`` files. The result is
    sorted by agent, scenario and file name, so the same files always give
    the same order.

    Raises:
        ConfigError: If ``source`` does not exist.
        SnapshotFormatError: If a file is not a valid snapshot.
    """
    path = Path(source)
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = sorted(path.rglob("*.json"))
    else:
        raise ConfigError(f"Snapshot source not found: {path}")
    snapshots = [(read_snapshot(f), f) for f in files]
    snapshots.sort(key=lambda item: (item[0].fingerprint.agent_id, item[0].scenario, item[1].name))
    return [snapshot for snapshot, _ in snapshots]


@dataclass(frozen=True)
class SnapshotResult:
    """One snapshot checked against a spec."""

    snapshot: Snapshot
    check: SpecCheck

    @property
    def passed(self) -> bool:
        return self.check.passed

    @property
    def failures(self) -> list[str]:
        """Human-readable failure lines, one per problem."""
        return self.check.failures()


@dataclass(frozen=True)
class CheckResult:
    """A spec checked against every snapshot of its producer.

    ``errors`` holds problems with the input itself, such as no snapshots for
    the producer; they fail the result, so nothing passes by being skipped.
    """

    spec: Spec
    cases: list[SnapshotResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors and all(case.passed for case in self.cases)

    @property
    def failed(self) -> list[SnapshotResult]:
        return [case for case in self.cases if not case.passed]


def check(
    spec: Spec,
    snapshots: list[Snapshot],
    expected: Mapping[str, Mapping[str, Any]] | None = None,
    policy_engine: PolicyEngine | None = None,
) -> CheckResult:
    """Check the snapshots of ``spec.producer`` against ``spec``.

    Snapshots of other agents are ignored. ``expected`` maps scenario names to
    exact output values for the producer (from scenario files).
    """
    checker = SpecChecker(policy_engine)
    own = [s for s in snapshots if s.fingerprint.agent_id == spec.producer]
    if not own:
        return CheckResult(
            spec=spec,
            errors=[
                f"No snapshots for '{spec.producer}', the producer of spec '{spec.name}'. "
                "Record them with 'handshake record'."
            ],
        )
    cases = [
        SnapshotResult(
            snapshot=s,
            check=checker.check(
                spec,
                s.output_data,
                s.input_data,
                dict((expected or {}).get(s.scenario) or {}),
            ),
        )
        for s in own
    ]
    return CheckResult(spec=spec, cases=cases)
