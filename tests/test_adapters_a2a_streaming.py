"""Tests for A2AAdapter streaming against a mocked SendStreamingMessage endpoint."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from agent_handshake import A2AAdapter
from agent_handshake.exceptions import AdapterError

BASE = "https://agent.example.com"
CARD = {
    "name": "Triage",
    "version": "3.1.0",
    "capabilities": {"streaming": True},
    "supportedInterfaces": [
        {"url": f"{BASE}/a2a/jsonrpc", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"},
    ],
}


def _status(state: str) -> dict[str, Any]:
    return {"statusUpdate": {"taskId": "t1", "contextId": "c1", "status": {"state": state}}}


def _artifact(*parts: dict[str, Any], append: bool = False, aid: str = "a1") -> dict[str, Any]:
    return {
        "artifactUpdate": {
            "taskId": "t1",
            "contextId": "c1",
            "artifact": {"artifactId": aid, "parts": list(parts)},
            "append": append,
        }
    }


TASK = {"task": {"id": "t1", "contextId": "c1", "status": {"state": "TASK_STATE_SUBMITTED"}}}


def _sse(*results: dict[str, Any]) -> str:
    """Each result as one SSE event; the JSON is split over two data lines."""
    events = []
    for result in results:
        text = json.dumps({"jsonrpc": "2.0", "id": "1", "result": result}, indent=1)
        head, _, tail = text.partition("\n")
        events.append(f"data: {head}\ndata: {tail.replace(chr(10), ' ')}\n\n")
    return ": keep-alive\n\n" + "".join(events)


class Server:
    def __init__(self, body: str, card: Any = CARD, content_type: str = "text/event-stream"):
        self.body = body
        self.card = card
        self.content_type = content_type
        self.posts: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=self.card)
        self.posts.append(request)
        return httpx.Response(
            200, content=self.body.encode(), headers={"content-type": self.content_type}
        )


async def _call(server: Server) -> Any:
    adapter = A2AAdapter(
        url=BASE,
        agent_id="triage-agent",
        streaming=True,
        transport=httpx.MockTransport(server.handler),
    )
    return await adapter.call({"message": "charged twice"})


class TestStreaming:
    async def test_events_fold_into_completed_task(self) -> None:
        server = Server(
            _sse(
                TASK,
                _status("TASK_STATE_WORKING"),
                _artifact({"data": {"category": "billing"}}),
                _artifact({"text": "Classified"}, append=True),
                _status("TASK_STATE_COMPLETED"),
            )
        )
        response = await _call(server)
        assert response.output == {"category": "billing", "text": "Classified"}
        assert response.metadata == {"task_id": "t1", "context_id": "c1"}
        [post] = server.posts
        assert json.loads(post.content)["method"] == "SendStreamingMessage"
        assert post.headers["accept"] == "text/event-stream"

    async def test_status_and_artifacts_without_task_event(self) -> None:
        server = Server(
            _sse(_artifact({"data": {"category": "billing"}}), _status("TASK_STATE_COMPLETED"))
        )
        assert (await _call(server)).output == {"category": "billing"}

    async def test_new_artifact_with_same_id_replaces_it(self) -> None:
        server = Server(
            _sse(
                _artifact({"text": "draft"}),
                _artifact({"text": "final"}),
                _status("TASK_STATE_COMPLETED"),
            )
        )
        assert (await _call(server)).output == {"text": "final"}

    async def test_message_reply(self) -> None:
        message = {"message": {"role": "ROLE_AGENT", "contextId": "c9", "parts": [{"text": "hi"}]}}
        response = await _call(Server(_sse(message)))
        assert response.output == {"text": "hi"}
        assert response.metadata == {"context_id": "c9"}

    async def test_stream_ends_before_completion(self) -> None:
        server = Server(_sse(TASK, _status("TASK_STATE_WORKING")))
        with pytest.raises(AdapterError, match="task ended in TASK_STATE_WORKING"):
            await _call(server)

    async def test_append_to_unknown_artifact(self) -> None:
        server = Server(_sse(_artifact({"text": "x"}, append=True)))
        with pytest.raises(AdapterError, match="append to unknown artifact 'a1'"):
            await _call(server)

    async def test_jsonrpc_error_event(self) -> None:
        error = {"jsonrpc": "2.0", "id": "1", "error": {"code": -32001, "message": "busy"}}
        server = Server(f"data: {json.dumps(error)}\n\n")
        with pytest.raises(AdapterError, match="A2A error -32001: busy"):
            await _call(server)

    async def test_error_that_is_not_an_object(self) -> None:
        server = Server(f"data: {json.dumps({'jsonrpc': '2.0', 'id': '1', 'error': 'busy'})}\n\n")
        with pytest.raises(AdapterError, match="A2A error: 'busy'"):
            await _call(server)

    async def test_event_value_that_is_not_an_object(self) -> None:
        with pytest.raises(AdapterError, match="stream event is not an object"):
            await _call(Server(_sse({"statusUpdate": "done"})))

    async def test_status_that_is_not_an_object(self) -> None:
        bad = {"statusUpdate": {"taskId": "t1", "status": "done"}}
        with pytest.raises(AdapterError, match="task status is not an object"):
            await _call(Server(_sse(bad)))

    async def test_artifact_that_is_not_an_object(self) -> None:
        bad = {"artifactUpdate": {"taskId": "t1", "artifact": "x"}}
        with pytest.raises(AdapterError, match="artifact is not an object"):
            await _call(Server(_sse(bad, _status("TASK_STATE_COMPLETED"))))

    async def test_part_that_is_not_an_object(self) -> None:
        with pytest.raises(AdapterError, match="part is not an object"):
            await _call(Server(_sse({"message": {"parts": ["text"]}})))

    async def test_plain_json_error_response(self) -> None:
        error = {"jsonrpc": "2.0", "id": "1", "error": {"code": -32600, "message": "bad"}}
        server = Server(json.dumps(error), content_type="application/json")
        with pytest.raises(AdapterError, match="A2A error -32600: bad"):
            await _call(server)

    async def test_sse_error_event(self) -> None:
        server = Server("event: error\ndata: overloaded\n\n")
        with pytest.raises(AdapterError, match="A2A stream error: overloaded"):
            await _call(server)

    async def test_empty_stream(self) -> None:
        with pytest.raises(AdapterError, match="ended without a task or message"):
            await _call(Server(": nothing\n\n"))

    async def test_unknown_event(self) -> None:
        with pytest.raises(AdapterError, match="unknown A2A stream event"):
            await _call(Server(_sse({"pushConfig": {}})))

    async def test_invalid_json(self) -> None:
        with pytest.raises(AdapterError, match=r"A2A stream from .* failed"):
            await _call(Server("data: {not json\n\n"))

    async def test_card_without_streaming(self) -> None:
        card = {**CARD, "capabilities": {}}
        with pytest.raises(AdapterError, match="does not declare streaming"):
            await _call(Server(_sse(TASK), card=card))
