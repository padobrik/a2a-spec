"""A2AAdapter against a real server built with the official a2a-sdk.

The server runs in-process through httpx's ASGI transport, so the test
exercises the actual SDK request parsing, task lifecycle and serialization
without opening a port.
"""

from __future__ import annotations

import hashlib
from typing import Any

import httpx
import pytest

pytest.importorskip("a2a.server.routes", reason="needs a2a-sdk[http-server]")

from a2a.server.agent_execution.agent_executor import AgentExecutor  # noqa: E402
from a2a.server.agent_execution.context import RequestContext  # noqa: E402
from a2a.server.events.event_queue import EventQueue  # noqa: E402
from a2a.server.request_handlers import DefaultRequestHandler  # noqa: E402
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes  # noqa: E402
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore  # noqa: E402
from a2a.server.tasks.task_updater import TaskUpdater  # noqa: E402
from a2a.types import (  # noqa: E402
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Part,
    Task,
    TaskState,
    TaskStatus,
)
from google.protobuf import json_format, struct_pb2  # noqa: E402
from starlette.applications import Starlette  # noqa: E402

from agent_handshake import A2AAdapter, SnapshotStore  # noqa: E402
from agent_handshake.exceptions import AdapterError  # noqa: E402
from agent_handshake.snapshot.recorder import Recorder  # noqa: E402

BASE = "http://agent.test"
RECEIPT = b"%PDF-1.7 receipt"


class TriageExecutor(AgentExecutor):
    """Classifies the incoming message; data in, data + text out."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        assert context.message and context.task_id and context.context_id
        await event_queue.enqueue_event(
            Task(
                id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                history=[context.message],
            )
        )
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.start_work()

        received = _received(context)
        text = received.get("message", "")
        if "fail" in text:
            await updater.failed(message=updater.new_agent_message([Part(text="model down")]))
            return
        if "receipt" in text:
            await updater.add_artifact(
                parts=[
                    Part(raw=RECEIPT, filename="receipt.pdf", media_type="application/pdf"),
                    Part(url="https://files.test/r.png", media_type="image/png"),
                ],
                name="receipt",
            )
            await updater.complete()
            return

        data = struct_pb2.Value()
        json_format.ParseDict(
            {"category": "billing" if "charge" in text else "general", "confidence": 0.9}, data
        )
        await updater.add_artifact(
            parts=[Part(data=data), Part(text=f"Classified: {text}")], name="triage"
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError


def _received(context: RequestContext) -> dict[str, Any]:
    """Input as the agent saw it: the data part if present, else the text."""
    assert context.message
    for part in context.message.parts:
        if part.HasField("data"):
            value = json_format.MessageToDict(part.data)
            assert isinstance(value, dict)
            return value
    return {"message": context.get_user_input()}


def _app() -> Starlette:
    card = AgentCard(
        name="Triage",
        description="Classifies support messages",
        version="2.4.0",
        supported_interfaces=[
            AgentInterface(
                url=f"{BASE}/a2a/jsonrpc", protocol_binding="JSONRPC", protocol_version="1.0"
            )
        ],
        capabilities=AgentCapabilities(),
        default_input_modes=["application/json", "text/plain"],
        default_output_modes=["application/json", "text/plain"],
        skills=[AgentSkill(id="triage", name="Triage", description="Classify", tags=["support"])],
    )
    handler = DefaultRequestHandler(
        agent_executor=TriageExecutor(), task_store=InMemoryTaskStore(), agent_card=card
    )
    routes = create_agent_card_routes(agent_card=card) + create_jsonrpc_routes(
        request_handler=handler, rpc_url="/a2a/jsonrpc"
    )
    return Starlette(routes=routes)


def _adapter(**kwargs: Any) -> A2AAdapter:
    return A2AAdapter(
        url=BASE, agent_id="triage-agent", transport=httpx.ASGITransport(app=_app()), **kwargs
    )


class TestA2AInterop:
    async def test_data_round_trip(self) -> None:
        resp = await _adapter().call({"message": "I was charged twice"})
        assert resp.output == {
            "category": "billing",
            "confidence": 0.9,
            "text": "Classified: I was charged twice",
        }
        assert resp.metadata is not None and resp.metadata["task_id"]

    async def test_text_round_trip(self) -> None:
        resp = await _adapter(text_field="message").call({"message": "where is my parcel"})
        assert resp.output["category"] == "general"
        assert resp.output["text"] == "Classified: where is my parcel"

    async def test_failed_task(self) -> None:
        with pytest.raises(AdapterError, match="task ended in TASK_STATE_FAILED: model down"):
            await _adapter().call({"message": "please fail"})

    async def test_file_parts(self) -> None:
        resp = await _adapter().call({"message": "send my receipt"})
        assert resp.output == {
            "files": [
                {
                    "filename": "receipt.pdf",
                    "mediaType": "application/pdf",
                    "size": len(RECEIPT),
                    "sha256": hashlib.sha256(RECEIPT).hexdigest(),
                },
                {"mediaType": "image/png", "url": "https://files.test/r.png"},
            ]
        }

    async def test_health_check(self) -> None:
        assert await _adapter().health_check()

    async def test_record_snapshot_with_card_version(self, tmp_path: Any) -> None:
        store = SnapshotStore(tmp_path)
        snapshot = await Recorder(store).record(
            _adapter(), "billing", {"message": "I was charged twice"}
        )
        assert snapshot.output_data["category"] == "billing"
        assert snapshot.metadata["agent_version"] == "2.4.0"
        assert store.load("triage-agent", "billing").output_data == snapshot.output_data
