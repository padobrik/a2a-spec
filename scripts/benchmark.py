"""Measure how many consumer field reads `handshake infer` finds on real projects.

Each project in benchmarks/<suite>/<project>/benchmark.yaml names a repository,
a commit and a list of cases. A case is one consumer function and the fields
it really reads from the producer's output (the expected list, written by
hand with a file:line for each field). The script fetches each repository at
its commit, runs the consumer analysis on every case and prints, per project
and in total: fields found, expected fields, and false fields (fields the
analysis reports that are not on the expected list).

There are two suites. `recon` holds the projects the analyzer was developed
against; `holdout` holds projects it was never tuned on. Each gets its own total.

    python scripts/benchmark.py                      # every suite
    python scripts/benchmark.py --suite holdout
    python scripts/benchmark.py --project crewai-flow-template -v
    python scripts/benchmark.py --repo-dir gpt-researcher=../gpt-researcher

Repositories are cached in .cache/benchmarks/. Exits 2 when a benchmark file
is invalid or a repository cannot be fetched; the counts never change the
exit code.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent_handshake.exceptions import HandshakeError
from agent_handshake.infer.consumer import analyze_consumer

ROOT = Path(__file__).resolve().parent.parent
SUITES = ("recon", "holdout")
BENCHMARKS = ROOT / "benchmarks"
CACHE = ROOT / ".cache" / "benchmarks"


@dataclass(frozen=True)
class CaseScore:
    """One consumer function compared with its expected fields."""

    case_id: str
    expected: frozenset[str]
    found: frozenset[str]
    error: str | None = None

    @property
    def hits(self) -> frozenset[str]:
        return self.expected & self.found

    @property
    def false(self) -> frozenset[str]:
        """Found fields not expected; a parent of an expected field is read with it."""
        return self.found - self.expected - _parents(self.expected)

    @property
    def missed(self) -> frozenset[str]:
        return self.expected - self.found


@dataclass
class ProjectScore:
    name: str
    cases: list[CaseScore] = field(default_factory=list)

    @property
    def hits(self) -> int:
        return sum(len(c.hits) for c in self.cases)

    @property
    def total(self) -> int:
        return sum(len(c.expected) for c in self.cases)

    @property
    def false(self) -> int:
        return sum(len(c.false) for c in self.cases)


def _parents(paths: frozenset[str]) -> frozenset[str]:
    """``a`` and ``a.b`` for ``a.b.c``; ``searches`` for ``searches[].query``."""
    found: set[str] = set()
    for path in paths:
        parts = path.replace("[]", "").split(".")
        found.update(".".join(parts[:n]) for n in range(1, len(parts)))
    return frozenset(found)


def dotted(path: tuple[str, ...]) -> str:
    """``("searches", "[]", "query")`` as ``searches[].query``; ``[]`` marks list items."""
    text = ""
    for key in path:
        text += key if key == "[]" else (f".{key}" if text else key)
    return text


def field_paths(
    path: str | Path, function: str, keys: frozenset[str] | None = None
) -> frozenset[str]:
    """Every field path the analysis finds, parents included, as in a spec.

    ``keys`` are the producer's output keys, as ``handshake infer`` passes them.
    """
    reads = analyze_consumer(path, function, keys).reads
    return frozenset(
        dotted(r.path[:n])
        for r in reads
        for n in range(1, len(r.path) + 1)
        if r.path[n - 1] != "[]"
    )


def producer_keys(project: Path, producer: str | None) -> frozenset[str]:
    """The output keys of the producer's snapshots in the benchmark project."""
    if not producer:
        return frozenset()
    keys: set[str] = set()
    for path in sorted((project / "handshake" / "snapshots" / producer).glob("*.json")):
        output = json.loads(path.read_text(encoding="utf-8")).get("output")
        if isinstance(output, dict):
            keys.update(output)
    return frozenset(keys)


def score_case(case: dict[str, Any], repo: Path, project: Path | None = None) -> CaseScore:
    """Run the analysis for one case; a case without a source finds nothing."""
    expected = frozenset(str(e["path"]) for e in case.get("expected") or [])
    source = case.get("source")
    if not source:
        return CaseScore(case["id"], expected, frozenset(), "no consumer function")
    file, function = str(source).rsplit(":", 1)
    target = repo / file
    with tempfile.TemporaryDirectory() as tmp:
        if case.get("replace"):
            # Template files are not valid code until rendered; render a copy.
            text = target.read_text(encoding="utf-8")
            for old, new in case["replace"]:
                text = text.replace(old, new)
            target = Path(tmp) / target.name
            target.write_text(text, encoding="utf-8")
        keys = producer_keys(project, case.get("producer")) if project else None
        try:
            found = field_paths(target, function, keys)
        except HandshakeError as e:
            # Name the file as the benchmark does, not by a temporary or local path.
            error = str(e).replace(str(target), file).replace(str(repo) + "/", "")
            return CaseScore(case["id"], expected, frozenset(), error)
    return CaseScore(case["id"], expected, found)


def _git(repo: Path, *args: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise OSError("git is required to fetch the benchmark repositories")
    # A fixed program with arguments built here, not a shell command.
    proc = subprocess.run(  # noqa: S603
        [git, "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def checkout(slug: str, repository: str, commit: str, cache: Path) -> Path:
    """The repository at ``commit``, fetched once into the cache."""
    repo = cache / slug
    if (repo / ".git").is_dir():
        if _git(repo, "rev-parse", "HEAD") == commit:
            return repo
        shutil.rmtree(repo)
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "remote", "add", "origin", repository)
    _git(repo, "fetch", "-q", "--depth", "1", "origin", commit)
    _git(repo, "checkout", "-q", "FETCH_HEAD")
    return repo


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("project", "repository", "commit", "cases"):
        if key not in data:
            raise ValueError(f"{path}: missing '{key}'")
    for case in data["cases"]:
        if "id" not in case or "expected" not in case:
            raise ValueError(f"{path}: every case needs 'id' and 'expected'")
    return data


def run(
    slugs: list[str], repo_dirs: dict[str, Path], cache: Path, benchmarks: Path = BENCHMARKS
) -> list[ProjectScore]:
    scores = []
    for slug in slugs:
        data = load(benchmarks / slug / "benchmark.yaml")
        repo = repo_dirs.get(slug) or checkout(slug, data["repository"], data["commit"], cache)
        project = ProjectScore(data["project"])
        folder = benchmarks / slug
        project.cases = [score_case(case, repo, folder) for case in data["cases"]]
        scores.append(project)
    return scores


def report(scores: list[ProjectScore], verbose: bool) -> str:
    width = max([len("project"), *(len(p.name) for p in scores)])
    lines = [f"{'project':<{width}} {'found':>6} {'total':>6} {'false':>6}"]
    for project in scores:
        lines.append(
            f"{project.name:<{width}} {project.hits:>6} {project.total:>6} {project.false:>6}"
        )
        if verbose:
            for case in project.cases:
                note = f"  ({case.error})" if case.error else ""
                lines.append(f"  {case.case_id}: {len(case.hits)}/{len(case.expected)}{note}")
                for name in sorted(case.missed):
                    lines.append(f"    missed {name}")
                for name in sorted(case.false):
                    lines.append(f"    false  {name}")
    hits = sum(p.hits for p in scores)
    total = sum(p.total for p in scores)
    false = sum(p.false for p in scores)
    share = f"{100 * hits / total:.0f}%" if total else "-"
    lines.append(f"{'total':<{width}} {hits:>6} {total:>6} {false:>6}   found {share}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suite", choices=SUITES, action="append", help="Only this suite.")
    parser.add_argument("--project", action="append", help="Only this project (repeatable).")
    parser.add_argument(
        "--repo-dir",
        action="append",
        default=[],
        metavar="PROJECT=DIR",
        help="Use a local checkout at the benchmark's commit instead of fetching.",
    )
    parser.add_argument("--cache", type=Path, default=CACHE)
    # A single suite directory elsewhere, for preparing a new suite.
    parser.add_argument("--benchmarks", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("-v", "--verbose", action="store_true", help="Show each case.")
    args = parser.parse_args(argv[1:])

    if args.benchmarks:
        suites = [(args.benchmarks.name, args.benchmarks)]
    else:
        suites = [(name, BENCHMARKS / name) for name in args.suite or SUITES]
    blocks = []
    try:
        repo_dirs = {k: Path(v) for k, v in (item.split("=", 1) for item in args.repo_dir)}
        for name, folder in suites:
            found = sorted(p.parent.name for p in folder.glob("*/benchmark.yaml"))
            slugs = [s for s in found if not args.project or s in args.project]
            if slugs:
                scores = run(slugs, repo_dirs, args.cache / name, folder)
                blocks.append(f"== {name}\n{report(scores, args.verbose)}")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as e:
        print(f"benchmark: {e}", file=sys.stderr)
        return 2
    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
