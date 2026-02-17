"""Tests for HTTPAdapter."""

from __future__ import annotations

import pytest

from a2a_spec.adapters.http_adapter import HTTPAdapter
from a2a_spec.exceptions import AdapterError


class TestHTTPAdapter:
    def test_metadata(self) -> None:
        adapter = HTTPAdapter(
            url="http://localhost:8000/agent", agent_id="http-agent", version="1.0"
        )
        meta = adapter.get_metadata()
        assert meta.agent_id == "http-agent"
        assert meta.version == "1.0"

    def test_metadata_with_optional_fields(self) -> None:
        adapter = HTTPAdapter(
            url="http://localhost:8000/agent",
            agent_id="http-agent",
            version="2.0",
            model="gpt-4",
            prompt_hash="xyz",
        )
        meta = adapter.get_metadata()
        assert meta.model == "gpt-4"
        assert meta.prompt_hash == "xyz"

    async def test_call_unreachable_raises(self) -> None:
        adapter = HTTPAdapter(
            url="http://127.0.0.1:19999/nonexistent",
            agent_id="bad-agent",
            version="1.0",
            timeout=1.0,
        )
        with pytest.raises(AdapterError, match="Request failed"):
            await adapter.call({"msg": "test"})

    async def test_health_check_unreachable(self) -> None:
        adapter = HTTPAdapter(
            url="http://127.0.0.1:19999/nonexistent",
            agent_id="bad-agent",
            version="1.0",
        )
        result = await adapter.health_check()
        assert result is False

    def test_custom_headers(self) -> None:
        adapter = HTTPAdapter(
            url="http://localhost:8000/agent",
            agent_id="test",
            version="1.0",
            headers={"Authorization": "Bearer token123"},
        )
        assert adapter._headers == {"Authorization": "Bearer token123"}

    def test_custom_timeout(self) -> None:
        adapter = HTTPAdapter(
            url="http://localhost:8000/agent",
            agent_id="test",
            version="1.0",
            timeout=5.0,
        )
        assert adapter._timeout == 5.0
