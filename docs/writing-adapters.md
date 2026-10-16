# Writing Adapters

Adapters wrap your agents so agent-handshake can call them during recording and testing.

## FunctionAdapter

For plain async Python functions:

```python
from agent_handshake import FunctionAdapter

async def my_agent(input_data: dict) -> dict:
    return {"category": "billing", "summary": "Customer reports billing issue"}

adapter = FunctionAdapter(
    fn=my_agent,
    agent_id="my-agent",
    version="1.0.0",
    model="gpt-4",
)
```

Requirements:
- Function must be `async`
- Must accept `dict` and return `dict`

## HTTPAdapter

For HTTP/REST agent endpoints:

```python
from agent_handshake import HTTPAdapter

adapter = HTTPAdapter(
    url="http://localhost:8000/agent",
    agent_id="my-agent",
    version="1.0.0",
    headers={"Authorization": "Bearer token"},
    timeout=30.0,
)
```

The endpoint must accept POST with JSON body and return JSON.

## A2AAdapter

For agents that implement the [A2A protocol](https://a2a-protocol.org) 1.0:

```python
from agent_handshake import A2AAdapter

adapter = A2AAdapter(
    url="https://triage.example.com",  # base URL or agent card URL
    agent_id="triage-agent",
    text_field=None,     # set to send input[text_field] as a text part
    json_text=False,     # parse a text-only JSON object reply as the output
    headers={"Authorization": "Bearer token"},
    timeout=60.0,
    streaming=False,     # True: use SendStreamingMessage (server-sent events)
)
```

- The Agent Card is fetched from `/.well-known/agent-card.json` (or the URL
  given) once per adapter; the first `JSONRPC` interface with protocol
  version `1.x` is used, including its `tenant`.
- Requests use `SendMessage` with `A2A-Version: 1.0` and block until the task
  finishes. With `streaming=True` they use `SendStreamingMessage`: the adapter
  reads the server-sent events, applies status and artifact updates to the
  task in order (an `append` update adds parts to its artifact), and checks
  the task when the stream ends. The Agent Card must declare
  `capabilities.streaming`. The snapshot is the same as without streaming.
- Output: object `data` parts are merged (conflicting keys are an error),
  other `data` values go under `"data"`, text under `"text"`, file parts
  under `"files"`. A file sent by URL keeps `url`; a file sent as bytes
  (`raw`) is stored as `size` and `sha256`, not as its content. `filename`
  and `mediaType` are kept when present.
- Tasks that end in any state other than completed raise `AdapterError`.
- Agents that only offer A2A 0.3 are rejected with a clear message.

## Frameworks

Agents built with LangChain, CrewAI or another framework need no special adapter.
Call the agent from an `async` function and wrap it with `FunctionAdapter`:

```python
from agent_handshake import FunctionAdapter

from agents.triage import chain  # a LangChain runnable


async def triage(data: dict) -> dict:
    return await chain.ainvoke(data)


adapter = FunctionAdapter(fn=triage, agent_id="triage-agent", version="1.0.0")
```

The function must return a dict or a string. If the framework returns a model
object, convert it first, for example with `result.model_dump()`.

An agent that returns plain text is recorded with the text as `output`. Its
spec can check the text with `structural: {type: string}` and `regex` policy
rules. A spec that expects an object fails on a text snapshot with "the output
is text, but the spec expects an object"; other specs still run.

## Custom Adapters

Subclass `AgentAdapter` for full control:

```python
from agent_handshake import AgentAdapter, AgentMetadata, AgentResponse

class MyAdapter(AgentAdapter):
    def get_metadata(self) -> AgentMetadata:
        return AgentMetadata(agent_id="my-agent", version="1.0")

    async def call(self, input_data: dict) -> AgentResponse:
        result = await my_custom_logic(input_data)
        return AgentResponse(output=result)
```

## Registering Adapters

Create `handshake/adapters/__init__.py` in your project (or point
`adapters_dir` in `handshake.yaml` at another package). `handshake record` runs
from the project root, so adapters can import your agent modules directly
(`from agents.triage import triage_agent`) or each other relatively
(`from .triage_adapter import triage_adapter`):

```python
ADAPTERS = {
    "triage-agent": triage_adapter,
    "resolution-agent": resolution_adapter,
}
```
