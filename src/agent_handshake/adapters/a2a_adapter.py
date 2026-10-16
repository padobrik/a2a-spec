"""Adapter for agents that speak the A2A protocol (version 1.0, JSON-RPC)."""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urljoin

import httpx

from agent_handshake.adapters.base import AgentAdapter, AgentMetadata, AgentResponse
from agent_handshake.exceptions import AdapterError

AGENT_CARD_PATH = "/.well-known/agent-card.json"
PROTOCOL_VERSION = "1.0"


class A2AAdapter(AgentAdapter):
    """Calls an A2A agent through its Agent Card and the JSON-RPC binding.

    The input dict is sent as one structured ``data`` part, or, with
    ``text_field``, that field's value is sent as a ``text`` part. The reply
    (a Message, or the artifacts of a completed Task) becomes the output
    dict: ``data`` parts holding objects are merged, ``text`` parts are joined
    under ``"text"``, and file parts (``raw`` or ``url``) are listed under
    ``"files"``. A ``url`` file keeps its URL; a ``raw`` file is described by
    its ``size`` and ``sha256`` instead of its bytes, so snapshots stay small.
    With ``json_text=True`` a text-only reply that is a JSON object is used as
    the output directly.

    With ``streaming=True`` the request uses ``SendStreamingMessage``; the
    status and artifact events are applied to the task in order, and the
    result is read once the stream ends. The Agent Card must declare
    ``capabilities.streaming``.

    Usage:
        adapter = A2AAdapter(
            url="https://triage.example.com",   # or the agent card URL
            agent_id="triage-agent",
        )
    """

    def __init__(
        self,
        url: str,
        agent_id: str,
        version: str | None = None,
        text_field: str | None = None,
        json_text: bool = False,
        headers: dict[str, str] | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
        streaming: bool = False,
    ) -> None:
        self._card_url = url if url.endswith(".json") else url.rstrip("/") + AGENT_CARD_PATH
        self._agent_id = agent_id
        self._version = version
        self._text_field = text_field
        self._json_text = json_text
        self._headers = headers or {}
        self._timeout = timeout
        self._transport = transport
        self._streaming = streaming
        self._card: dict[str, Any] | None = None
        self._endpoint: tuple[str, str | None] | None = None

    def get_metadata(self) -> AgentMetadata:
        """Return metadata; the version comes from the Agent Card once fetched."""
        version = self._version or (self._card or {}).get("version") or "unknown"
        return AgentMetadata(agent_id=self._agent_id, version=str(version))

    async def health_check(self) -> bool:
        """Return True if the Agent Card can be fetched and offers JSON-RPC 1.0."""
        try:
            async with self._client() as client:
                await self._resolve(client)
        except AdapterError:
            return False
        return True

    async def call(self, input_data: dict[str, Any]) -> AgentResponse:
        """Send the input as an A2A message and return the agent's reply.

        Raises:
            AdapterError: If the card or endpoint is unusable, the agent returns
                a JSON-RPC error, or the task does not complete.
        """
        start = time.monotonic()
        async with self._client() as client:
            rpc_url, tenant = await self._resolve(client)
            params: dict[str, Any] = {"message": self._message(input_data)}
            if tenant:
                params["tenant"] = tenant
            if self._streaming:
                result = await self._stream(client, rpc_url, params)
            else:
                reply = await self._post(client, rpc_url, self._rpc("SendMessage", params))
                result = self._result(reply)
        latency = (time.monotonic() - start) * 1000

        meta: dict[str, Any] = {}
        if "task" in result:
            task = result["task"]
            parts = self._task_parts(task)
            meta = {"task_id": task.get("id"), "context_id": task.get("contextId")}
        elif "message" in result:
            parts = result["message"].get("parts") or []
            meta = {"context_id": result["message"].get("contextId")}
        else:
            raise AdapterError(self._agent_id, "A2A reply has neither 'task' nor 'message'")

        output, text = self._to_output(parts)
        return AgentResponse(output=output, raw_text=text, latency_ms=latency, metadata=meta)

    @staticmethod
    def _rpc(method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params}

    def _result(self, reply: dict[str, Any]) -> dict[str, Any]:
        if "error" in reply:
            err = reply["error"] or {}
            if not isinstance(err, dict):
                raise AdapterError(self._agent_id, f"A2A error: {err!r}")
            raise AdapterError(
                self._agent_id, f"A2A error {err.get('code')}: {err.get('message', '')}"
            )
        result = reply.get("result") or {}
        if not isinstance(result, dict):
            raise AdapterError(self._agent_id, "A2A result is not an object")
        return result

    async def _stream(
        self, client: httpx.AsyncClient, url: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Send SendStreamingMessage and fold the events into one task or message."""
        if not ((self._card or {}).get("capabilities") or {}).get("streaming"):
            raise AdapterError(
                self._agent_id, f"Agent card {self._card_url} does not declare streaming"
            )
        task: dict[str, Any] | None = None
        message: dict[str, Any] | None = None
        body = self._rpc("SendStreamingMessage", params)
        try:
            async with client.stream(
                "POST", url, json=body, headers={"Accept": "text/event-stream"}
            ) as resp:
                resp.raise_for_status()
                async for reply in self._events(resp):
                    result = self._result(reply)
                    if any(not isinstance(value, dict) for value in result.values()):
                        raise AdapterError(self._agent_id, "A2A stream event is not an object")
                    if "message" in result:
                        message = result["message"]
                    elif "task" in result:
                        task = copy.deepcopy(result["task"])
                    elif "statusUpdate" in result:
                        update = result["statusUpdate"]
                        task = task or {
                            "id": update.get("taskId"),
                            "contextId": update.get("contextId"),
                        }
                        task["status"] = update.get("status") or {}
                    elif "artifactUpdate" in result:
                        update = result["artifactUpdate"]
                        task = task or {
                            "id": update.get("taskId"),
                            "contextId": update.get("contextId"),
                        }
                        self._apply_artifact(task, update)
                    else:
                        raise AdapterError(
                            self._agent_id, f"unknown A2A stream event with keys {sorted(result)}"
                        )
        except (httpx.HTTPError, ValueError) as e:
            raise AdapterError(self._agent_id, f"A2A stream from {url} failed: {e}") from e

        if message is not None:
            return {"message": message}
        if task is not None:
            return {"task": task}
        raise AdapterError(self._agent_id, "A2A stream ended without a task or message")

    async def _events(self, resp: httpx.Response) -> AsyncIterator[dict[str, Any]]:
        """JSON-RPC replies from a server-sent event stream.

        A server may answer with plain JSON instead, for example an error.
        """
        if "text/event-stream" not in resp.headers.get("content-type", ""):
            yield self._object(json.loads(await resp.aread()))
            return
        event = "message"
        data: list[str] = []
        async for line in resp.aiter_lines():
            if not line:
                if data:
                    payload = "\n".join(data)
                    if event == "error":
                        raise AdapterError(self._agent_id, f"A2A stream error: {payload}")
                    yield self._object(json.loads(payload))
                event, data = "message", []
            elif line.startswith(":"):
                continue
            else:
                key, _, value = line.partition(":")
                value = value[1:] if value.startswith(" ") else value
                if key == "data":
                    data.append(value)
                elif key == "event":
                    event = value
        if data:
            yield self._object(json.loads("\n".join(data)))

    def _object(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise AdapterError(self._agent_id, "A2A reply is not a JSON-RPC object")
        return value

    def _apply_artifact(self, task: dict[str, Any], update: dict[str, Any]) -> None:
        """Add or replace an artifact, or append parts to it, as a2a-sdk does."""
        artifact = copy.deepcopy(update.get("artifact") or {})
        artifacts: list[dict[str, Any]] = task.setdefault("artifacts", [])
        index = next(
            (
                i
                for i, a in enumerate(artifacts)
                if a.get("artifactId") == artifact.get("artifactId")
            ),
            None,
        )
        if not update.get("append"):
            if index is None:
                artifacts.append(artifact)
            else:
                artifacts[index] = artifact
        elif index is not None:
            artifacts[index].setdefault("parts", []).extend(artifact.get("parts") or [])
        else:
            raise AdapterError(
                self._agent_id,
                f"append to unknown artifact {artifact.get('artifactId')!r}",
            )

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            headers={**self._headers, "A2A-Version": PROTOCOL_VERSION},
            transport=self._transport,
        )

    async def _resolve(self, client: httpx.AsyncClient) -> tuple[str, str | None]:
        if self._endpoint is not None:
            return self._endpoint
        try:
            resp = await client.get(self._card_url)
            resp.raise_for_status()
            card = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise AdapterError(
                self._agent_id, f"Cannot load agent card {self._card_url}: {e}"
            ) from e
        if not isinstance(card, dict):
            raise AdapterError(self._agent_id, f"Agent card {self._card_url} is not an object")

        interfaces = card.get("supportedInterfaces") or []
        for iface in interfaces:
            if iface.get("protocolBinding") == "JSONRPC" and str(
                iface.get("protocolVersion", "")
            ).startswith("1."):
                self._card = card
                self._endpoint = (urljoin(self._card_url, iface["url"]), iface.get("tenant"))
                return self._endpoint

        offered = [
            f"{i.get('protocolBinding')} {i.get('protocolVersion')}" for i in interfaces
        ] or [f"A2A {card.get('protocolVersion', 'unknown')}"]
        raise AdapterError(
            self._agent_id,
            f"Agent card {self._card_url} offers {', '.join(offered)}; "
            f"A2AAdapter needs a JSONRPC interface for A2A {PROTOCOL_VERSION}",
        )

    async def _post(
        self, client: httpx.AsyncClient, url: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            reply = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise AdapterError(self._agent_id, f"A2A request to {url} failed: {e}") from e
        if not isinstance(reply, dict):
            raise AdapterError(self._agent_id, "A2A reply is not a JSON-RPC object")
        return reply

    def _message(self, input_data: dict[str, Any]) -> dict[str, Any]:
        if self._text_field is None:
            part: dict[str, Any] = {"data": input_data, "mediaType": "application/json"}
        else:
            value = input_data.get(self._text_field)
            if not isinstance(value, str):
                raise AdapterError(
                    self._agent_id, f"text_field '{self._text_field}' is missing or not a string"
                )
            part = {"text": value}
        return {"messageId": str(uuid.uuid4()), "role": "ROLE_USER", "parts": [part]}

    def _task_parts(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        status = task.get("status") or {}
        state = status.get("state")
        status_parts = (status.get("message") or {}).get("parts") or []
        if state != "TASK_STATE_COMPLETED":
            detail = " ".join(p["text"] for p in status_parts if "text" in p)
            raise AdapterError(self._agent_id, f"task ended in {state}: {detail}".rstrip(": "))
        parts = [p for a in task.get("artifacts") or [] for p in a.get("parts") or []]
        return parts or status_parts

    def _to_output(self, parts: list[dict[str, Any]]) -> tuple[dict[str, Any], str | None]:
        if not parts:
            raise AdapterError(self._agent_id, "A2A reply contains no parts")
        output: dict[str, Any] = {}
        texts: list[str] = []
        loose: list[Any] = []
        files: list[dict[str, Any]] = []
        for part in parts:
            if "text" in part:
                texts.append(part["text"])
            elif "data" in part:
                data = part["data"]
                if not isinstance(data, dict):
                    loose.append(data)
                    continue
                clash = output.keys() & data.keys()
                if clash:
                    raise AdapterError(
                        self._agent_id, f"data parts disagree on key(s) {sorted(clash)}"
                    )
                output.update(data)
            elif "raw" in part or "url" in part:
                files.append(self._file(part))
            else:
                raise AdapterError(self._agent_id, f"unknown part with keys {sorted(part)}")

        text = "\n".join(texts) if texts else None
        if text is not None and not output and not loose and not files and self._json_text:
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed, text
        if loose:
            self._put(output, "data", loose[0] if len(loose) == 1 else loose)
        if text is not None:
            self._put(output, "text", text)
        if files:
            self._put(output, "files", files)
        return output, text

    def _file(self, part: dict[str, Any]) -> dict[str, Any]:
        entry: dict[str, Any] = {}
        for key in ("filename", "mediaType"):
            if key in part:
                entry[key] = part[key]
        if "url" in part:
            entry["url"] = part["url"]
            return entry
        try:
            content = base64.b64decode(part["raw"], validate=True)
        except (binascii.Error, TypeError, ValueError) as e:
            raise AdapterError(self._agent_id, f"file part has invalid base64 'raw': {e}") from e
        entry["size"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
        return entry

    def _put(self, output: dict[str, Any], key: str, value: Any) -> None:
        if key in output:
            raise AdapterError(self._agent_id, f"reply already has a '{key}' field")
        output[key] = value
