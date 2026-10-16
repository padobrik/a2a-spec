"""Print the CHANGELOG section of one version, for the GitHub release notes.

Exits 1 when CHANGELOG.md has no section for the version, or the section is
empty, so a release cannot start without its notes.

    python scripts/changelog_section.py 0.8.0 > release-notes.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def section(text: str, version: str) -> str | None:
    """The body under ``## [version]``, without link definitions, or None."""
    heading = re.compile(rf"^## \[{re.escape(version)}\][^\n]*\n", re.MULTILINE)
    match = heading.search(text)
    if match is None:
        return None
    rest = text[match.end() :]
    following = re.search(r"^## \[", rest, re.MULTILINE)
    body = rest[: following.start()] if following else rest
    body = re.sub(r"^\[[^\]]+\]: \S+[ \t]*$", "", body, flags=re.MULTILINE)
    return body.strip() or None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: changelog_section.py VERSION", file=sys.stderr)
        return 2
    version = argv[1].removeprefix("v")
    body = section(CHANGELOG.read_text(encoding="utf-8"), version)
    if body is None:
        print(f"CHANGELOG.md has no notes for {version}", file=sys.stderr)
        return 1
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
