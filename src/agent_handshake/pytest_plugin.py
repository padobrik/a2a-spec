"""pytest plugin: run agent-handshake contracts as ordinary pytest tests.

It turns on by itself when handshake.yaml is in the working directory or a
parent up to the rootdir. Enable it elsewhere with ``--handshake`` or by
setting ``handshake_config`` in the pytest ini options. Every spec YAML under
the configured ``specs_dir`` then becomes a test file with one test per
recorded producer snapshot, and the ``handshake_check`` fixture validates live
outputs inside your own tests.
"""

from __future__ import annotations

import warnings
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from agent_handshake.api import check as check_snapshots
from agent_handshake.api import load_snapshots
from agent_handshake.config.loader import load_config
from agent_handshake.config.settings import HandshakeConfig
from agent_handshake.exceptions import ConfigError, SnapshotFormatError
from agent_handshake.infer.check import check_inferred_spec
from agent_handshake.project import load_scenarios
from agent_handshake.snapshot.store import Snapshot, SnapshotStore
from agent_handshake.spec.checker import SpecCheck, SpecChecker
from agent_handshake.spec.loader import load_all_specs, load_spec
from agent_handshake.spec.schema import Spec

_STATE = pytest.StashKey["_A2AState | None"]()


class _A2AState:
    def __init__(self, root: Path, config_path: Path | None) -> None:
        self.root = root
        self.config: HandshakeConfig = load_config(config_path)
        self.specs_dir = self._resolve(self.config.specs_dir)
        self.store = SnapshotStore(self._resolve(self.config.storage.path))
        scenarios_config = self.config.model_copy(
            update={"scenarios_dir": str(self._resolve(self.config.scenarios_dir))}
        )
        try:
            self.scenarios = {sc.name: sc for sc in load_scenarios(scenarios_config)}
        except ConfigError:
            self.scenarios = {}
        self._snapshots: dict[str, list[Snapshot]] = {}

    def snapshots_of(self, producer: str) -> list[Snapshot]:
        """The snapshots of one producer, read once per session.

        Each producer's directory is read on its own, so a broken file fails
        only the specs of that producer.

        Raises:
            SnapshotFormatError: If a snapshot file of this producer is not valid.
        """
        if producer not in self._snapshots:
            directory = self.store.base_dir / producer
            found = load_snapshots(directory) if directory.is_dir() else []
            self._snapshots[producer] = [s for s in found if s.fingerprint.agent_id == producer]
        return self._snapshots[producer]

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else (self.root / p).resolve()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("agent-handshake")
    group.addoption(
        "--handshake", action="store_true", help="Run agent-handshake contracts as tests."
    )
    group.addoption("--handshake-config", help="Path to handshake.yaml (implies --handshake).")
    parser.addini("handshake_config", "Path to handshake.yaml; setting it enables the plugin.")
    parser.addini(
        "handshake_enabled",
        "Set to false to keep the plugin off even when handshake.yaml is found.",
        type="bool",
        default=True,
    )


def pytest_configure(config: pytest.Config) -> None:
    # Relative paths follow the same rule as the handshake CLI (the working
    # directory), except an ini setting, which is relative to its ini file.
    root = config.invocation_params.dir
    config_path = config.getoption("--handshake-config")
    if config_path is None and config.getini("handshake_config"):
        config_path = config.getini("handshake_config")
        if config.inipath is not None:
            root = config.inipath.parent
    explicit = config.getoption("--handshake") or config_path is not None
    # A handshake.yaml between the working directory and the rootdir turns the
    # plugin on without any flag.
    found = _nearest_project(config) if config.getini("handshake_enabled") else None
    if not explicit and found is None:
        config.stash[_STATE] = None
        return
    if not explicit and found is not None:
        root = found
    resolved = (root / config_path) if config_path else None
    if resolved is None:
        default = root / "handshake.yaml"
        resolved = default if default.exists() else None
    state = _A2AState(root, resolved)
    config.stash[_STATE] = state
    _collect_specs_dir(config, state.specs_dir)


def _nearest_project(config: pytest.Config) -> Path | None:
    """The nearest directory with handshake.yaml, from the working directory up to the rootdir.

    In a monorepo each project keeps its own handshake.yaml; running pytest in
    a project directory uses that project's file.
    """
    rootpath = config.rootpath
    start = config.invocation_params.dir
    candidates = [start, *start.parents] if start.is_relative_to(rootpath) else [rootpath]
    for directory in candidates:
        if (directory / "handshake.yaml").exists():
            return directory
        if directory == rootpath:
            break
    return None


def _collect_specs_dir(config: pytest.Config, specs_dir: Path) -> None:
    """Add the specs directory to the run when pytest would not reach it.

    Paths named on the command line are left alone; with testpaths or no
    paths, the specs are collected too unless an argument already covers them.
    """
    if config.args_source == pytest.Config.ArgsSource.ARGS or not specs_dir.is_dir():
        return
    base = config.invocation_params.dir
    for arg in config.args:
        path = (base / arg.split("::", 1)[0]).resolve()
        if path == specs_dir or path in specs_dir.parents:
            return
    config.args.append(str(specs_dir))


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> pytest.Collector | None:
    state = parent.config.stash.get(_STATE, None)
    if state is None or file_path.suffix not in (".yaml", ".yml"):
        return None
    if not file_path.resolve().is_relative_to(state.specs_dir):
        return None
    return SpecFile.from_parent(parent, path=file_path)


def _enabled_state(config: pytest.Config) -> _A2AState:
    """The plugin state; spec items exist only while the plugin is enabled."""
    state = config.stash[_STATE]
    if state is None:
        raise RuntimeError("the agent-handshake plugin is not enabled")
    return state


class SpecFile(pytest.File):
    """A spec YAML file; yields one item per recorded producer snapshot."""

    def collect(self) -> Iterator[pytest.Item]:
        state = _enabled_state(self.config)
        spec = load_spec(self.path)
        if spec.inferred_from:
            yield ConsumerCodeItem.from_parent(self, name="consumer_code", spec=spec)
        try:
            own = state.snapshots_of(spec.producer)
        except SnapshotFormatError as e:
            yield BrokenSnapshotItem.from_parent(self, name="snapshots", error=e)
            return
        if not own:
            yield MissingSnapshots.from_parent(self, name=spec.name, spec=spec)
        counts = Counter(s.scenario for s in own)
        for snapshot in own:
            name = snapshot.scenario
            if counts[name] > 1:  # several recordings of one scenario
                name = f"{name}[{snapshot.fingerprint.key}]"
            yield SnapshotItem.from_parent(self, name=name, spec=spec, snapshot=snapshot)


class SnapshotItem(pytest.Item):
    """Validates one recorded snapshot against its spec."""

    def __init__(self, *, spec: Spec, snapshot: Snapshot, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.spec = spec
        self.snapshot = snapshot

    def runtest(self) -> None:
        state = _enabled_state(self.config)
        scenario = state.scenarios.get(self.snapshot.scenario)
        expected = scenario.expectations.get(self.spec.producer) if scenario else None
        result = check_snapshots(
            self.spec, [self.snapshot], {self.snapshot.scenario: expected or {}}
        )
        [case] = result.cases
        if not case.passed:
            raise ContractViolationError(case.check)

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException], style: Any = None) -> str:
        # A broken snapshot file is reported by its message, not a traceback.
        if isinstance(excinfo.value, ContractViolationError | SnapshotFormatError):
            return str(excinfo.value)
        return str(super().repr_failure(excinfo, style=style))

    def reportinfo(self) -> tuple[Path, int | None, str]:
        return self.path, None, f"{self.spec.name} / {self.name}"


class ConsumerCodeItem(pytest.Item):
    """Fails when the consumer code reads fields its inferred spec misses."""

    def __init__(self, *, spec: Spec, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.spec = spec

    def runtest(self) -> None:
        result = check_inferred_spec(self.spec)
        for warning in result.warnings:
            warnings.warn(f"{self.spec.name}: {warning}", UserWarning, stacklevel=1)
        if not result.passed:
            lines = [f"spec '{self.spec.name}' is out of date with {self.spec.inferred_from}:"]
            lines += [f"  {failure}" for failure in result.failures]
            lines.append("  Regenerate it with 'handshake infer ... --force'.")
            raise SpecOutOfDateError("\n".join(lines))

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException], style: Any = None) -> str:
        if isinstance(excinfo.value, SpecOutOfDateError):
            return str(excinfo.value)
        return str(super().repr_failure(excinfo, style=style))

    def reportinfo(self) -> tuple[Path, int | None, str]:
        return self.path, None, f"{self.spec.name} / consumer_code"


class BrokenSnapshotItem(pytest.Item):
    """Fails with the error of a snapshot file that is not valid."""

    def __init__(self, *, error: SnapshotFormatError, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.error = error

    def runtest(self) -> None:
        raise self.error

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException], style: Any = None) -> str:
        return str(excinfo.value)

    def reportinfo(self) -> tuple[Path, int | None, str]:
        return self.path, None, "snapshots"


class SpecOutOfDateError(AssertionError):
    """An inferred spec no longer covers what its consumer reads."""


class MissingSnapshots(pytest.Item):
    """Placeholder reporting a spec whose producer has no snapshots."""

    def __init__(self, *, spec: Spec, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.spec = spec

    def runtest(self) -> None:
        # Nothing to check is a failure, not a skip: a skip would let the spec pass unnoticed.
        raise MissingSnapshotsError(
            f"No snapshots for '{self.spec.producer}', the producer of spec "
            f"'{self.spec.name}'. Record them with 'handshake record'."
        )

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException], style: Any = None) -> str:
        if isinstance(excinfo.value, MissingSnapshotsError):
            return str(excinfo.value)
        return str(super().repr_failure(excinfo, style=style))


class MissingSnapshotsError(AssertionError):
    """A spec's producer has no snapshots to check."""


class ContractViolationError(AssertionError):
    """An output broke its contract; the message lists every failure."""

    def __init__(self, result: SpecCheck) -> None:
        lines = [f"contract '{result.spec.name}' violated:"]
        lines += [f"  {line}" for line in result.failures()]
        super().__init__("\n".join(lines))
        self.result = result


@pytest.fixture
def handshake_check(request: pytest.FixtureRequest) -> Callable[..., SpecCheck]:
    """Validate an output against a spec by name; fails the test on violation.

    Usage::

        def test_triage(handshake_check):
            output = run_triage({"message": "charged twice"})
            handshake_check("triage-to-resolution", output, {"message": "charged twice"})
    """
    state = request.config.stash.get(_STATE, None)
    if state is None:
        pytest.fail(
            "handshake_check needs the agent-handshake plugin enabled: put handshake.yaml "
            "in the working directory or above it up to the rootdir, or pass --handshake "
            "or --handshake-config"
        )
    specs = {s.name: s for s in load_all_specs(state.specs_dir)}
    checker = SpecChecker()

    def check(
        spec_name: str, output: dict[str, Any], input_data: dict[str, Any] | None = None
    ) -> SpecCheck:
        if spec_name not in specs:
            pytest.fail(f"unknown spec '{spec_name}'; known: {', '.join(sorted(specs))}")
        result = checker.check(specs[spec_name], output, input_data or {})
        if not result.passed:
            raise ContractViolationError(result)
        return result

    return check
