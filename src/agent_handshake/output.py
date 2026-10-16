"""The value an agent returns: an object (a dict) or plain text."""

from __future__ import annotations

from typing import Any

AgentOutput = dict[str, Any] | str
