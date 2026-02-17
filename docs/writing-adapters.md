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

Create `a2a_spec/adapters/__init__.py` in your project:

```python
ADAPTERS = {
    "triage-agent": triage_adapter,
    "resolution-agent": resolution_adapter,
}
```
