"""Tests for A2AAdapter against a mocked A2A 1.0 JSON-RPC server."""

from __future__ import annotations

import base64
import hashlib
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
    "supportedInterfaces": [
        {"url": f"{BASE}/a2a/rest", "protocolBinding": "HTTP+JSON", "protocolVersion": "1.0"},
        {"url": f"{BASE}/a2a/jsonrpc", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"},
    ],
}


def _task(state: str, artifacts: list[Any] | None = None, status_text: str = "") -> dict[str, Any]:
    status: dict[str, Any] = {"state": state}
    if status_text:
        status["message"] = {"role": "ROLE_AGENT", "parts": [{"text": status_text}]}
    return {"task": {"id": "t1", "contextId": "c1", "status": status, "artifacts": artifacts or []}}


def _artifact(*parts: dict[str, Any]) -> dict[str, Any]:
    return {"artifactId": "a1", "parts": list(parts)}


class Server:
    """Records requests and answers card + SendMessage calls."""

    def __init__(self, result: Any = None, card: Any = CARD, error: Any = None) -> None:
        self.card = card
        self.result = result
        self.error = error
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "GET":
            if request.url.path != "/.well-known/agent-card.json" and not str(request.url).endswith(
                "custom-card.json"
            ):
                return httpx.Response(404)
            return httpx.Response(200, json=self.card)
        body = json.loads(request.content)
        reply: dict[str, Any] = {"jsonrpc": "2.0", "id": body["id"]}
        if self.error is not None:
            reply["error"] = self.error
        else:
            reply["result"] = self.result
        return httpx.Response(200, json=reply)

    def rpc_body(self) -> dict[str, Any]:
        [post] = [r for r in self.requests if r.method == "POST"]
        return dict(json.loads(post.content))


def _adapter(server: Server, **kwargs: Any) -> A2AAdapter:
    kwargs.setdefault("url", BASE)
    return A2AAdapter(
        agent_id="triage-agent", transport=httpx.MockTransport(server.handler), **kwargs
    )


async def _call(server: Server, **kwargs: Any) -> Any:
    return await _adapter(server, **kwargs).call({"message": "charged twice"})


class TestRequest:
    async def test_sends_data_part_over_jsonrpc_1_0(self) -> None:
        server = Server(result={"message": {"role": "ROLE_AGENT", "parts": [{"text": "ok"}]}})
        await _call(server)

        post = [r for r in server.requests if r.method == "POST"][0]
        assert str(post.url) == f"{BASE}/a2a/jsonrpc"
        assert post.headers["A2A-Version"] == "1.0"
        body = server.rpc_body()
        assert body["jsonrpc"] == "2.0"
        assert body["method"] == "SendMessage"
        message = body["params"]["message"]
        assert message["role"] == "ROLE_USER"
        assert message["messageId"]
        assert message["parts"] == [
            {"data": {"message": "charged twice"}, "mediaType": "application/json"}
        ]

    async def test_text_field_sends_text_part(self) -> None:
        server = Server(result={"message": {"parts": [{"text": "ok"}]}})
        await _call(server, text_field="message")
        assert server.rpc_body()["params"]["message"]["parts"] == [{"text": "charged twice"}]

    async def test_text_field_missing(self) -> None:
        server = Server(result={"message": {"parts": [{"text": "ok"}]}})
        with pytest.raises(AdapterError, match="text_field 'body'"):
            await _call(server, text_field="body")

    async def test_tenant_and_custom_headers(self) -> None:
        card = {
            **CARD,
            "supportedInterfaces": [
                {
                    "url": "/rpc",
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "1.0",
                    "tenant": "acme",
                }
            ],
        }
        server = Server(result={"message": {"parts": [{"text": "ok"}]}}, card=card)
        await _call(server, headers={"Authorization": "Bearer x"})
        post = [r for r in server.requests if r.method == "POST"][0]
        assert str(post.url) == f"{BASE}/rpc"
        assert post.headers["Authorization"] == "Bearer x"
        assert server.rpc_body()["params"]["tenant"] == "acme"

    async def test_explicit_card_url(self) -> None:
        server = Server(result={"message": {"parts": [{"text": "ok"}]}})
        await _call(server, url=f"{BASE}/custom-card.json")
        assert str(server.requests[0].url) == f"{BASE}/custom-card.json"

    async def test_card_fetched_once(self) -> None:
        server = Server(result={"message": {"parts": [{"text": "ok"}]}})
        adapter = _adapter(server)
        await adapter.call({"a": "1"})
        await adapter.call({"a": "2"})
        assert [r.method for r in server.requests] == ["GET", "POST", "POST"]


class TestCard:
    async def test_v0_3_card_rejected_clearly(self) -> None:
        card = {"name": "Old", "url": f"{BASE}/rpc", "protocolVersion": "0.3.0"}
        with pytest.raises(AdapterError, match=r"offers A2A 0\.3\.0.*needs a JSONRPC interface"):
            await _call(Server(card=card))

    async def test_no_jsonrpc_interface(self) -> None:
        card = {**CARD, "supportedInterfaces": CARD["supportedInterfaces"][:1]}
        with pytest.raises(AdapterError, match=r"offers HTTP\+JSON 1\.0"):
            await _call(Server(card=card))

    async def test_card_not_found(self) -> None:
        with pytest.raises(AdapterError, match="Cannot load agent card"):
            await _call(Server(), url=f"{BASE}/missing.json")

    async def test_health_check(self) -> None:
        assert await _adapter(Server()).health_check()
        assert not await _adapter(Server(card={"name": "x"})).health_check()

    async def test_version_from_card_after_call(self) -> None:
        adapter = _adapter(Server(result={"message": {"parts": [{"text": "ok"}]}}))
        assert adapter.get_metadata().version == "unknown"
        await adapter.call({})
        assert adapter.get_metadata().version == "3.1.0"
        assert adapter.get_metadata().agent_id == "triage-agent"

    def test_explicit_version_wins(self) -> None:
        assert _adapter(Server(), version="9").get_metadata().version == "9"


class TestReply:
    async def test_completed_task_artifact_data(self) -> None:
        result = _task("TASK_STATE_COMPLETED", [_artifact({"data": {"category": "billing"}})])
        resp = await _call(Server(result=result))
        assert resp.output == {"category": "billing"}
        assert resp.metadata == {"task_id": "t1", "context_id": "c1"}
        assert resp.latency_ms is not None

    async def test_data_parts_merged_and_text_added(self) -> None:
        result = _task(
            "TASK_STATE_COMPLETED",
            [
                _artifact({"data": {"category": "billing"}}, {"text": "Looks like"}),
                _artifact({"data": {"priority": "high"}}, {"text": "a double charge."}),
            ],
        )
        resp = await _call(Server(result=result))
        assert resp.output == {
            "category": "billing",
            "priority": "high",
            "text": "Looks like\na double charge.",
        }
        assert resp.raw_text == "Looks like\na double charge."

    async def test_conflicting_data_parts(self) -> None:
        result = _task(
            "TASK_STATE_COMPLETED",
            [_artifact({"data": {"category": "billing"}}, {"data": {"category": "shipping"}})],
        )
        with pytest.raises(AdapterError, match=r"disagree on key\(s\) \['category'\]"):
            await _call(Server(result=result))

    async def test_message_text_reply(self) -> None:
        result = {"message": {"role": "ROLE_AGENT", "parts": [{"text": "hello"}]}}
        resp = await _call(Server(result=result))
        assert resp.output == {"text": "hello"}

    async def test_non_object_data(self) -> None:
        result = {"message": {"parts": [{"data": ["a", "b"]}]}}
        assert (await _call(Server(result=result))).output == {"data": ["a", "b"]}

    async def test_json_text(self) -> None:
        result = {"message": {"parts": [{"text": '{"category": "billing"}'}]}}
        assert (await _call(Server(result=result), json_text=True)).output == {
            "category": "billing"
        }
        assert (await _call(Server(result=result))).output == {"text": '{"category": "billing"}'}

    async def test_json_text_ignores_non_objects(self) -> None:
        result = {"message": {"parts": [{"text": "[1, 2]"}]}}
        assert (await _call(Server(result=result), json_text=True)).output == {"text": "[1, 2]"}

    async def test_completed_task_reply_in_status_message(self) -> None:
        result = _task("TASK_STATE_COMPLETED", status_text="done")
        assert (await _call(Server(result=result))).output == {"text": "done"}

    @pytest.mark.parametrize(
        "state", ["TASK_STATE_FAILED", "TASK_STATE_INPUT_REQUIRED", "TASK_STATE_REJECTED"]
    )
    async def test_unfinished_task_raises_with_status(self, state: str) -> None:
        result = _task(state, status_text="model unavailable")
        with pytest.raises(AdapterError, match=f"task ended in {state}: model unavailable"):
            await _call(Server(result=result))

    async def test_jsonrpc_error(self) -> None:
        server = Server(error={"code": -32009, "message": "Version not supported"})
        with pytest.raises(AdapterError, match="A2A error -32009: Version not supported"):
            await _call(server)

    async def test_empty_result(self) -> None:
        with pytest.raises(AdapterError, match="neither 'task' nor 'message'"):
            await _call(Server(result={}))

    async def test_file_parts_listed(self) -> None:
        raw = base64.b64encode(b"%PDF-1.7").decode()
        parts = [
            {"text": "see attached"},
            {"url": "https://x/y.png", "mediaType": "image/png"},
            {"raw": raw, "filename": "invoice.pdf", "mediaType": "application/pdf"},
        ]
        response = await _call(Server(result={"message": {"parts": parts}}))
        assert response.output == {
            "text": "see attached",
            "files": [
                {"mediaType": "image/png", "url": "https://x/y.png"},
                {
                    "filename": "invoice.pdf",
                    "mediaType": "application/pdf",
                    "size": 8,
                    "sha256": hashlib.sha256(b"%PDF-1.7").hexdigest(),
                },
            ],
        }

    async def test_invalid_raw_file(self) -> None:
        result = {"message": {"parts": [{"raw": "not base64!"}]}}
        with pytest.raises(AdapterError, match="invalid base64"):
            await _call(Server(result=result))

    async def test_files_key_clash(self) -> None:
        parts = [{"data": {"files": []}}, {"url": "https://x/y.png"}]
        with pytest.raises(AdapterError, match="already has a 'files' field"):
            await _call(Server(result={"message": {"parts": parts}}))

    async def test_json_text_kept_as_text_next_to_files(self) -> None:
        parts = [{"text": '{"a": 1}'}, {"url": "https://x/y.png"}]
        response = await _call(Server(result={"message": {"parts": parts}}), json_text=True)
        assert response.output["text"] == '{"a": 1}'

    async def test_unknown_part(self) -> None:
        with pytest.raises(AdapterError, match="unknown part"):
            await _call(Server(result={"message": {"parts": [{"metadata": {}}]}}))

    async def test_no_parts(self) -> None:
        with pytest.raises(AdapterError, match="no parts"):
            await _call(Server(result=_task("TASK_STATE_COMPLETED")))
