"""Hashing utilities."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_dict(data: dict[str, Any]) -> str:
    """Deterministic SHA256 hash of a dict."""
    content = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


def short_hash(data: dict[str, Any], length: int = 12) -> str:
    """Short deterministic hash of a dict."""
    return hash_dict(data)[:length]


def hash_string(text: str) -> str:
    """SHA256 hash of a string."""
    return hashlib.sha256(text.encode()).hexdigest()
