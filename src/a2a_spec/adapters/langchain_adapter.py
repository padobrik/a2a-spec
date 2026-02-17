"""Adapter for LangChain runnables."""

from __future__ import annotations

import time
from typing import Any

from a2a_spec.adapters.base import AgentAdapter, AgentMetadata, AgentResponse
from a2a_spec.exceptions import AdapterError


class LangChainAdapter(AgentAdapter):
    """Wraps a LangChain Runnable as an agent adapter.

    Requires the `langchain-core` package to be installed.

    Usage:
        from langchain_core.runnables import RunnableLambda

        runnable = RunnableLambda(lambda x: {"category": "billing"})
        adapter = LangChainAdapter(
            runnable=runnable,
            agent_id="triage-agent",
            version="1.0.0",
        )
    """

    def __init__(
        self,
        runnable: Any,
        agent_id: str,
        version: str,
        model: str | None = None,
        prompt_hash: str | None = None,
    ) -> None:
        try:
            from langchain_core.runnables import Runnable  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "langchain-core is required for LangChainAdapter. "
                "Install with: pip install a2a-spec[langchain]"
            ) from e

        self._runnable = runnable
        self._agent_id = agent_id
        self._version = version
        self._model = model
        self._prompt_hash = prompt_hash

    def get_metadata(self) -> AgentMetadata:
        """Return metadata for this LangChain adapter."""
        return AgentMetadata(
            agent_id=self._agent_id,
            version=self._version,
            model=self._model,
            prompt_hash=self._prompt_hash,
        )

    async def call(self, input_data: dict[str, Any]) -> AgentResponse:
        """Invoke the LangChain runnable.

        Args:
            input_data: Input dict to pass to the runnable.

        Returns:
            AgentResponse with the runnable's output.

        Raises:
            AdapterError: If the runnable call fails.
        """
        start = time.monotonic()
        try:
            result = await self._runnable.ainvoke(input_data)
        except Exception as e:
            raise AdapterError(self._agent_id, f"LangChain call failed: {e}") from e

        latency = (time.monotonic() - start) * 1000

        # Normalize result to dict
        if isinstance(result, dict):
            output = result
        elif isinstance(result, str):
            output = {"text": result}
        elif hasattr(result, "dict"):
            output = result.dict()
        elif hasattr(result, "content"):
            output = {"content": str(result.content)}
        else:
            output = {"result": str(result)}

        return AgentResponse(output=output, latency_ms=latency)
