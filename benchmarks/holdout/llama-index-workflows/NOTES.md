# Notes: llama-index-workflows

## The example

At this commit the repository ships no workflow example as a `.py` file (the docs
examples are notebooks, and the standalone workflows package lives in another
repository). The project's main multi-agent pipeline is `AgentWorkflow` in
`llama-index-core/llama_index/core/agent/workflow/multi_agent_workflow.py`, and its
sample run is `test_workflow_execution` in
`llama-index-core/tests/agent/workflow/test_multi_agent_workflow.py`: a root agent
`retriever` (FunctionAgent) hands off to `calculator` (ReActAgent), which calls the tool
`add`. I picked it because it has two model-calling agents, a handoff between them, and
six `@step` stages that pass typed `Event` objects and shared context state.
`AGUIChatWorkflow` (ag-ui protocol integration) was the other candidate; it has only one
model-calling step.

Producers and consumers are the workflow steps (plus the `handoff` tool). The step
`run_agent_step` is the one that calls the model, through the current agent.

| link | producer | consumer | data |
|---|---|---|---|
| L1 | init_run | setup_agent | `AgentInput` event |
| L2 | setup_agent | run_agent_step | `AgentSetup` event |
| L3 | run_agent_step | parse_agent_output | `AgentOutput` event (model reply) |
| L4 | parse_agent_output | call_tool | `ToolCall` event, one per tool call |
| L5 | call_tool | aggregate_tool_results | `ToolCallResult` events, collected |
| L6 | aggregate_tool_results | setup_agent | `AgentInput` event (next turn) |
| L7 | parse_agent_output | setup_agent | `AgentInput` event (retry) |
| L8 | handoff (tool) | aggregate_tool_results | context state key `next_agent` |

8 cases, 38 expected fields.

## Data forms

- Typed Pydantic events (`Event` subclasses in `workflow_events.py`) holding nested
  Pydantic models: `ChatMessage` lists, `ToolSelection` lists, `ToolOutput`.
- Shared context state (`ctx.store`): `next_agent` written by the handoff tool, and the
  `current_tool_calls` list, which stores the `ToolCallResult` events and is read back in
  the same consumer.
- Model text sits inside `ChatMessage.blocks[].text`; the consumers mostly pass message
  lists whole to the model.

## Unusual points and assumptions

- Several consumer reads happen in methods called on the agent object
  (`take_step`, `finalize`, `handle_tool_call_results`), which dispatch to FunctionAgent
  or ReActAgent. The example uses both, so reads in both implementations count.
- `content` on `ChatMessage` and `ToolOutput` is a computed property, not a dumped
  field. The consumers read it as an attribute, so it is a field and the snapshots carry it.
- In L3, `structured_response` is written by the consumer before it is read, so it is
  not listed. `raw` is excluded from the event and is not read.
- `setup_agent` is the consumer of three links (L1, L6, L7), with the same reads each time.
- L8 treats the handoff tool's state write as its output; its return text reaches the
  workflow through `call_tool` (L5) as `tool_output.content`.
- Workflow configuration kept in state by `_init_context` (agents, max_iterations,
  memory) is not agent output and is not a case. The final `StopEvent` result read by
  the test is not a case either.
