"""Tests for LangChainAdapter."""

from __future__ import annotations

import warnings

import pytest

pytest.importorskip("langchain_core")

from langchain_core.messages import AIMessage  # noqa: E402
from langchain_core.runnables import RunnableLambda  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from agent_handshake.adapters.langchain_adapter import LangChainAdapter  # noqa: E402
from agent_handshake.exceptions import AdapterError  # noqa: E402


class _Triage(BaseModel):
    category: str
    confidence: float


def _adapter(fn: object) -> LangChainAdapter:
    return LangChainAdapter(runnable=RunnableLambda(fn), agent_id="triage", version="1.0")


class TestLangChainAdapter:
    def test_exported_from_package(self) -> None:
        from agent_handshake import LangChainAdapter as Exported

        assert Exported is LangChainAdapter

    async def test_dict_output(self) -> None:
        resp = await _adapter(lambda x: {"category": "billing"}).call({"message": "hi"})
        assert resp.output == {"category": "billing"}
        assert resp.latency_ms is not None

    async def test_str_output(self) -> None:
        resp = await _adapter(lambda x: "plain text").call({"message": "hi"})
        assert resp.output == {"text": "plain text"}

    async def test_chat_message_output_uses_content(self) -> None:
        resp = await _adapter(lambda x: AIMessage(content="hello")).call({"message": "hi"})
        assert resp.output == {"content": "hello"}

    async def test_pydantic_output_uses_model_dump(self) -> None:
        adapter = _adapter(lambda x: _Triage(category="billing", confidence=0.9))
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            resp = await adapter.call({"message": "hi"})
        assert resp.output == {"category": "billing", "confidence": 0.9}

    async def test_runnable_error_wrapped(self) -> None:
        def boom(x: object) -> object:
            raise RuntimeError("model down")

        with pytest.raises(AdapterError, match="model down"):
            await _adapter(boom).call({"message": "hi"})
