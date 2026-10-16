"""Adapter for HTTP/REST agent endpoints."""

from __future__ import annotations

import time
from typing import Any

import httpx

from a2a_spec.adapters.base import AgentAdapter, AgentMetadata, AgentResponse
from a2a_spec.exceptions import AdapterError


class HTTPAdapter(AgentAdapter):
    """Wraps an HTTP endpoint as an agent adapter.

    The endpoint must accept POST with JSON body and return JSON.

    Usage:
        adapter = HTTPAdapter(
            url="http://localhost:8000/triage",
            agent_id="triage-agent",
            version="1.0.0",
        )
    """

    def __init__(
        self,
        url: str,
        agent_id: str,
        version: str,
        model: str | None = None,
        prompt_hash: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._url = url
        self._agent_id = agent_id
        self._version = version
        self._model = model
        self._prompt_hash = prompt_hash
        self._headers = headers or {}
        self._timeout = timeout

    def get_metadata(self) -> AgentMetadata:
        """Return metadata for this HTTP adapter."""
        return AgentMetadata(
            agent_id=self._agent_id,
            version=self._version,
            model=self._model,
            prompt_hash=self._prompt_hash,
        )

    async def call(self, input_data: dict[str, Any]) -> AgentResponse:
        """Call the HTTP endpoint with the given input.

        Args:
            input_data: JSON-serializable dict to POST.

        Returns:
            AgentResponse with the parsed JSON response.

        Raises:
            AdapterError: If the HTTP call fails or response is invalid.
        """
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._url,
                    json=input_data,
                    headers=self._headers,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise AdapterError(
                self._agent_id,
                f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            ) from e
        except httpx.RequestError as e:
            raise AdapterError(self._agent_id, f"Request failed: {e}") from e

        latency = (time.monotonic() - start) * 1000

        try:
            output = resp.json()
        except ValueError as e:
            raise AdapterError(self._agent_id, "Response is not valid JSON") from e

        if not isinstance(output, dict):
            raise AdapterError(
                self._agent_id,
                f"Expected JSON object, got {type(output).__name__}",
            )

        return AgentResponse(output=output, latency_ms=latency)

    async def health_check(self) -> bool:
        """Check if the HTTP endpoint is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self._url.rsplit("/", 1)[0] + "/health")
                return resp.status_code == 200
        except httpx.RequestError:
            return False
