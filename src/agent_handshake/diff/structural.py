"""Structural comparison between two agent outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldDiff:
    """A single field-level difference.

    Immutable — represents a recorded fact about a detected change.
    """

    field: str
    change_type: str  # "added", "removed", "changed", "type_changed"
    old_value: Any = None
    new_value: Any = None
    detail: str = ""


def structural_diff(old: dict[str, Any], new: dict[str, Any]) -> list[FieldDiff]:
    """Compare two dicts and return field-level differences.

    Args:
        old: The baseline output.
        new: The current output.

    Returns:
        List of FieldDiff objects for each difference found.
    """
    diffs: list[FieldDiff] = []
    all_keys = set(old.keys()) | set(new.keys())

    for key in sorted(all_keys):
        old_val = old.get(key)
        new_val = new.get(key)

        if key not in old:
            diffs.append(
                FieldDiff(
                    field=key,
                    change_type="added",
                    new_value=new_val,
                    detail=f"Field '{key}' was added",
                )
            )
        elif key not in new:
            diffs.append(
                FieldDiff(
                    field=key,
                    change_type="removed",
                    old_value=old_val,
                    detail=f"Field '{key}' was removed",
                )
            )
        elif type(old_val) != type(new_val):  # noqa: E721
            diffs.append(
                FieldDiff(
                    field=key,
                    change_type="type_changed",
                    old_value=old_val,
                    new_value=new_val,
                    detail=(
                        f"Type changed from {type(old_val).__name__} to {type(new_val).__name__}"
                    ),
                )
            )
        elif old_val != new_val:
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                # Recurse into nested dicts, prefixing the field path.
                # FieldDiff is frozen so we construct new instances rather than mutating.
                nested = structural_diff(old_val, new_val)
                diffs.extend(
                    FieldDiff(
                        field=f"{key}.{d.field}",
                        change_type=d.change_type,
                        old_value=d.old_value,
                        new_value=d.new_value,
                        detail=d.detail,
                    )
                    for d in nested
                )
            else:
                diffs.append(
                    FieldDiff(
                        field=key,
                        change_type="changed",
                        old_value=old_val,
                        new_value=new_val,
                        detail="Value changed",
                    )
                )

    return diffs
