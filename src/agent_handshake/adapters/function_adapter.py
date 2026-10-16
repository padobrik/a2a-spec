"""Adapter for plain Python async functions."""

from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any

from a2a_spec.adapters.base import AgentAdapter, AgentMetadata, AgentResponse
from a2a_spec.exceptions import AdapterError


class FunctionAdapter(AgentAdapter):
    """Wraps an async Python function as an agent adapter.

    Usage:
        async def my_agent(input_data: dict) -> dict:
            # your agent logic
            return {"category": "billing"}

        adapter = FunctionAdapter(
            fn=my_agent,
            agent_id="triage-agent",
            version="1.0.0",
        )
    """

    def __init__(
        self,
        fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        agent_id: str,
        version: str,
        model: str | None = None,
        prompt_hash: str | None = None,
    ) -> None:
        if not callable(fn):
            raise AdapterError(agent_id, f"Expected callable, got {type(fn).__name__}")
        if not inspect.iscoroutinefunction(fn):
            raise AdapterError(agent_id, "Function must be async (use 'async def')")

        self._fn = fn
        self._agent_id = agent_id
        self._version = version
        self._model = model
        self._prompt_hash = prompt_hash

    def get_metadata(self) -> AgentMetadata:
        """Return metadata for this function adapter."""
        return AgentMetadata(
            agent_id=self._agent_id,
            version=self._version,
            model=self._model,
            prompt_hash=self._prompt_hash,
        )

    async def call(self, input_data: dict[str, Any]) -> AgentResponse:
        """Call the wrapped async function.

        Args:
            input_data: Input dict to pass to the function.

        Returns:
            AgentResponse with the function's return value.

        Raises:
            AdapterError: If the function call fails or returns wrong type.
        """
        start = time.monotonic()
        try:
            result = await self._fn(input_data)
        except Exception as e:
            raise AdapterError(self._agent_id, f"Agent call failed: {e}") from e

        latency = (time.monotonic() - start) * 1000

        if not isinstance(result, dict):
            raise AdapterError(
                self._agent_id,
                f"Agent must return dict, got {type(result).__name__}",
            )

        return AgentResponse(output=result, latency_ms=latency)
