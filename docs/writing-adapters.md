# Writing Adapters

Adapters wrap your agents so a2a-spec can call them during recording and testing.

## FunctionAdapter

For plain async Python functions:

```python
from a2a_spec import FunctionAdapter

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
from a2a_spec import HTTPAdapter

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
from a2a_spec import A2AAdapter

adapter = A2AAdapter(
    url="https://triage.example.com",  # base URL or agent card URL
    agent_id="triage-agent",
    text_field=None,     # set to send input[text_field] as a text part
    json_text=False,     # parse a text-only JSON object reply as the output
    headers={"Authorization": "Bearer token"},
    timeout=60.0,
)
```

- The Agent Card is fetched from `/.well-known/agent-card.json` (or the URL
  given) once per adapter; the first `JSONRPC` interface with protocol
  version `1.x` is used, including its `tenant`.
- Requests use `SendMessage` with `A2A-Version: 1.0` and block until the task
  finishes. Streaming is not used.
- Output: object `data` parts are merged (conflicting keys are an error),
  other `data` values go under `"data"`, text under `"text"`. File parts are
  not supported yet.
- Tasks that end in any state other than completed raise `AdapterError`.
- Agents that only offer A2A 0.3 are rejected with a clear message.

## Custom Adapters

Subclass `AgentAdapter` for full control:

```python
from a2a_spec import AgentAdapter, AgentMetadata, AgentResponse

class MyAdapter(AgentAdapter):
    def get_metadata(self) -> AgentMetadata:
        return AgentMetadata(agent_id="my-agent", version="1.0")

    async def call(self, input_data: dict) -> AgentResponse:
        result = await my_custom_logic(input_data)
        return AgentResponse(output=result)
```

## Registering Adapters

Create `a2a_spec/adapters/__init__.py` in your project (or point
`adapters_dir` in `a2a-spec.yaml` at another package). `a2aspec record` runs
from the project root, so adapters can import your agent modules directly
(`from agents.triage import triage_agent`) or each other relatively
(`from .triage_adapter import triage_adapter`):

```python
ADAPTERS = {
    "triage-agent": triage_adapter,
    "resolution-agent": resolution_adapter,
}
```
