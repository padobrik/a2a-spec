"""Shared type aliases."""

from __future__ import annotations

from typing import Any, Protocol

# Common type aliases used across the codebase
JsonDict = dict[str, Any]


class ValidatorFn(Protocol):
    """Protocol for custom policy validator functions."""

    def __call__(self, output: dict[str, Any], input_data: dict[str, Any]) -> tuple[bool, str]: ...
