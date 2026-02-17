"""Tests for FunctionAdapter."""

from __future__ import annotations

import pytest

from a2a_spec.adapters.function_adapter import FunctionAdapter
from a2a_spec.exceptions import AdapterError


class TestFunctionAdapter:
    def test_valid_async_function(self) -> None:
        async def my_agent(data: dict) -> dict:
            return {"result": "ok"}

        adapter = FunctionAdapter(fn=my_agent, agent_id="test", version="1.0")
        assert adapter.get_metadata().agent_id == "test"

    def test_sync_function_raises(self) -> None:
        def sync_fn(data: dict) -> dict:
            return {"result": "ok"}

        with pytest.raises(AdapterError, match="async"):
            FunctionAdapter(fn=sync_fn, agent_id="test", version="1.0")

    def test_non_callable_raises(self) -> None:
        with pytest.raises(AdapterError, match="callable"):
            FunctionAdapter(fn="not a function", agent_id="test", version="1.0")  # type: ignore

    async def test_call_returns_response(self) -> None:
        async def my_agent(data: dict) -> dict:
            return {"category": "billing"}

        adapter = FunctionAdapter(fn=my_agent, agent_id="test", version="1.0")
        resp = await adapter.call({"msg": "hello"})
        assert resp.output == {"category": "billing"}
        assert resp.latency_ms is not None
        assert resp.latency_ms >= 0

    async def test_call_non_dict_raises(self) -> None:
        async def bad_agent(data: dict) -> str:  # type: ignore
            return "not a dict"

        adapter = FunctionAdapter(fn=bad_agent, agent_id="test", version="1.0")
        with pytest.raises(AdapterError, match="dict"):
            await adapter.call({})

    async def test_call_exception_wrapped(self) -> None:
        async def failing_agent(data: dict) -> dict:
            raise ValueError("boom")

        adapter = FunctionAdapter(fn=failing_agent, agent_id="test", version="1.0")
        with pytest.raises(AdapterError, match="boom"):
            await adapter.call({})

    def test_metadata_fields(self) -> None:
        async def my_agent(data: dict) -> dict:
            return {}

        adapter = FunctionAdapter(
            fn=my_agent, agent_id="a", version="2.0", model="gpt-4", prompt_hash="abc"
        )
        meta = adapter.get_metadata()
        assert meta.version == "2.0"
        assert meta.model == "gpt-4"
        assert meta.prompt_hash == "abc"

    async def test_health_check_default(self) -> None:
        async def my_agent(data: dict) -> dict:
            return {}

        adapter = FunctionAdapter(fn=my_agent, agent_id="test", version="1.0")
        assert await adapter.health_check() is True
