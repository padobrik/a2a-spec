"""The recall case index and its dev/holdout split."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

CASES = Path(__file__).resolve().parent.parent / "benchmarks" / "cases"
HOLDOUT_MAX = 14


def _rows(name: str) -> list[dict[str, str]]:
    with (CASES / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def test_index_has_39_cases_with_sources() -> None:
    rows = _rows("index.tsv")
    assert [int(r["id"]) for r in rows] == list(range(1, 40))
    assert all(r["project"] and r["ref"] and r["summary"] for r in rows)
    assert {r["visibility"] for r in rows} == {"static", "runtime"}


def test_split_follows_the_documented_method() -> None:
    sizes = Counter(r["project"] for r in _rows("index.tsv"))
    split = {r["project"]: r["split"] for r in _rows("split.tsv")}
    assert set(split) == set(sizes)
    holdout: set[str] = set()
    count = 0
    for project in sorted(sizes, key=lambda p: hashlib.sha256(p.encode()).hexdigest()):
        if count + sizes[project] <= HOLDOUT_MAX:
            holdout.add(project)
            count += sizes[project]
    assert {p for p, s in split.items() if s == "holdout"} == holdout
    assert {p for p, s in split.items() if s == "dev"} == set(sizes) - holdout
    assert (count, sum(sizes.values()) - count) == (14, 25)
