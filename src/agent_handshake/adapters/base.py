"""Base adapter interface for wrapping any agent."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentMetadata:
    """Identification and configuration of an agent."""

    agent_id: str
    version: str
    model: str | None = None
    prompt_hash: str | None = None
    tools: list[str] = field(default_factory=list)


@dataclass
class AgentResponse:
    """Structured response from an agent call."""

    output: dict[str, Any]
    raw_text: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    token_usage: dict[str, int] | None = None
    latency_ms: float | None = None
    metadata: dict[str, Any] | None = None


class AgentAdapter(ABC):
    """Abstract base class for agent adapters.

    Implement this to wrap your agent (LangChain, CrewAI, plain function,
    HTTP service, etc.) so a2a-spec can call it during recording and testing.
    """

    @abstractmethod
    def get_metadata(self) -> AgentMetadata:
        """Return agent identification and configuration.

        This is called to identify the agent in snapshots and reports.
        The prompt_hash field is particularly important — it allows
        a2a-spec to detect when a prompt has changed and invalidate
        stale snapshots.
        """
        ...

    @abstractmethod
    async def call(self, input_data: dict[str, Any]) -> AgentResponse:
        """Execute the agent with the given input.

        Args:
            input_data: Arbitrary dict passed to the agent.

        Returns:
            AgentResponse with at minimum the output dict populated.

        Raises:
            AdapterError: If the agent call fails.
        """
        ...

    async def health_check(self) -> bool:
        """Optional health check. Returns True if agent is reachable."""
        return True
