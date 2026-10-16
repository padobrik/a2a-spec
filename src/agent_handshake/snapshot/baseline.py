"""Read committed snapshots from git to use as the diff baseline."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from agent_handshake.exceptions import ConfigError
from agent_handshake.snapshot.store import Snapshot

logger = logging.getLogger(__name__)


class GitBaseline:
    """Snapshots as they were at a git revision.

    ``handshake record`` overwrites snapshot files in place, so the baseline
    for a diff is the committed version of the same file, not another file
    in the working tree.
    """

    def __init__(self, store_dir: str | Path, ref: str = "HEAD") -> None:
        self.store_dir = Path(store_dir).resolve()
        self.ref = ref
        try:
            top = self._git("rev-parse", "--show-toplevel", cwd=self._existing_dir())
        except ConfigError as e:
            raise ConfigError(
                f"Snapshots in {self.store_dir} are not in a git repository. "
                "'handshake diff' compares recorded snapshots against their committed "
                "version; commit them first."
            ) from e
        self.root = Path(top.strip()).resolve()
        try:
            self._git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        except ConfigError as e:
            raise ConfigError(f"Unknown git revision '{ref}'") from e

    def load(self, path: Path) -> Snapshot | None:
        """Return the committed version of a snapshot file, or None if new."""
        rel = Path(path).resolve().relative_to(self.root).as_posix()
        try:
            content = self._git("show", f"{self.ref}:{rel}")
        except ConfigError:
            return None
        return Snapshot.from_dict(json.loads(content))

    def files(self, agent_dir: Path) -> list[Path]:
        """Snapshot files under ``agent_dir`` that exist at the revision."""
        rel = Path(agent_dir).resolve().relative_to(self.root).as_posix()
        out = self._git("ls-tree", "-r", "--name-only", self.ref, "--", f"{rel}/")
        return [self.root / line for line in out.splitlines() if line.endswith(".json")]

    def _existing_dir(self) -> Path:
        path = self.store_dir
        while not path.exists():
            path = path.parent
        return path

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        git = shutil.which("git")
        if git is None:
            raise ConfigError("git is required for 'handshake diff'")
        # A fixed program with arguments built here, not a shell command.
        proc = subprocess.run(  # noqa: S603
            [git, *args],
            cwd=cwd or self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = proc.stderr.strip() or f"git {args[0]} failed"
            logger.debug("git %s failed: %s", " ".join(args), detail)
            raise ConfigError(f"git {' '.join(args)}: {detail}")
        return proc.stdout
