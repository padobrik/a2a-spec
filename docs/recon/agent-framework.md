# Microsoft Agent Framework

Run on 2026-10-17 with agent-handshake 0.9.0 from PyPI. The snapshots and specs were written by hand in a local work directory and are not committed; each one's source is given below.

- Repository: https://github.com/microsoft/agent-framework (successor of AutoGen)
- Commit: 9127b89
- Example: `python/samples/03-workflows/control-flow/switch_case_edge_group.py`
- Framework: Microsoft Agent Framework (workflows: `WorkflowBuilder`, `@executor`, `AgentExecutor`)
- Language: Python

The example classifies one email and routes it. `store_email` saves the email in
workflow state and sends it as a chat message to a spam detection agent. The agent
answers with structured output (Pydantic `DetectionResultAgent`, JSON text).
`to_detection_result` parses that JSON and sends a dataclass `DetectionResult` to a
switch-case edge group. "NotSpam" goes to `submit_to_email_assistant`, which loads the
email from state and sends it to an email assistant agent; `finalize_and_send` parses
that agent's Pydantic `EmailResponse`. "Spam" goes to `handle_spam`. Anything else goes
to `handle_uncertain`, which also loads the email from state.

Why this sample: data passes between executors as a Pydantic model (lines 59-64,
67-71) and a dataclass (lines 74-79), one structured output is routed to three
consumers (lines 205-212), and it also uses shared workflow state (lines 103-104).
That covers the typical data forms of the `03-workflows` samples in one file of 241
lines. `multi_selection_edge_group.py` has the same forms with more branches, so it
would add length but no new forms.

All line numbers below are in `python/samples/03-workflows/control-flow/switch_case_edge_group.py`
unless a different file is named.

## 1. How the agents are linked

Edges are declared at lines 201-216.

| link | producer | consumer | data form | file:line |
|---|---|---|---|---|
| L1 | `store_email` | `spam_detection_agent` (`AgentExecutor.run`) | dataclass `AgentExecutorRequest` holding the email as free chat text | send 107-109, edge 203; consumer `python/packages/core/agent_framework/_workflows/_agent_executor.py:379-392` |
| L2 | `spam_detection_agent` | `to_detection_result` | `AgentExecutorResponse`; the Pydantic structured output is a JSON string in `response.agent_response.text` | schema 59-64, 176; edge 204; read 115-117 |
| L3 | `to_detection_result` | `submit_to_email_assistant` | dataclass `DetectionResult` (switch case "NotSpam") | send 117, edge 208, read 123, 127 |
| L4 | `to_detection_result` | `handle_spam` | dataclass `DetectionResult` (case "Spam") | edge 209, read 143-144 |
| L5 | `to_detection_result` | `handle_uncertain` | dataclass `DetectionResult` (Default) | edge 210, read 152-155 |
| L6 | `submit_to_email_assistant` | `email_assistant_agent` (`AgentExecutor.run`) | dataclass `AgentExecutorRequest` holding the email as free chat text | send 128-130, edge 213 |
| L7 | `email_assistant_agent` | `finalize_and_send` | `AgentExecutorResponse`; Pydantic `EmailResponse` as JSON text | schema 67-71, 190; edge 214; read 136-137 |
| L8 | `store_email` | `to_detection_result` | shared workflow state, key `current_email_id` (str) | set 104, get 116 |
| L9 | `store_email` | `submit_to_email_assistant` | shared workflow state, key `email:<id>`, dataclass `Email` | set 103, get 127, read 129 |
| L10 | `store_email` | `handle_uncertain` | shared workflow state, key `email:<id>`, dataclass `Email` | set 103, get 153, read 155 |

Count: 10 links. 7 are message edges (L1-L7), 3 go through shared workflow state
(L8-L10). The switch-case predicate `condition` (line 92-94) also reads
`DetectionResult.spam_decision`; it is part of the edge, not an agent, so it is not
counted as a link, but `infer` was tried on it too.

## 2. Does the producer -> consumer model fit?

Partly. The graph is a clear set of producer -> consumer edges, and each consumer is a
function whose first data parameter is the producer's message, so `--source
file:function` points at the right code. But the messages are dataclass or Pydantic
objects, not dicts. Every read is attribute access (`detection.email_id`), which
`infer` does not support. The agents' structured output travels as a JSON string
inside a framework object (`response.agent_response.text`), so the real fields are
behind a `model_validate_json` call. Three links do not travel on the edge at all:
they go through `ctx.set_state` / `ctx.get_state`, and `infer` only looks at the
first data parameter. Snapshots can describe the data (a dataclass maps cleanly to a
JSON object), and `handshake test` works on a hand-written spec.

## 3. What infer found

All runs used a local work directory with a `handshake.yaml` that has only `project_name`.
11 snapshots under `handshake/snapshots/` were written by `scripts/make_snapshots.py`
(three scenarios: not_spam, spam, uncertain). Sources:

- Email texts: `python/samples/03-workflows/resources/email.txt`, `spam.txt`,
  `ambiguous_email.txt` (the sample reads `ambiguous_email.txt` at line 219-224).
- Shapes: `AgentExecutorRequest` and `AgentExecutorResponse` fields from
  `python/packages/core/agent_framework/_workflows/_agent_executor.py:206-233`;
  `DetectionResultAgent`, `EmailResponse`, `DetectionResult` from lines 59-79.
  `Message` objects are shown as `{"role", "contents"}`, as built at lines 108, 129.
- `spam_decision` values are the three `Literal` values (line 63). `reason` and
  `response` are example strings (any `str` is valid). `email_id` values are fixed
  UUID4 strings, the form made at line 102.

`$SRC` = `python/samples/03-workflows/control-flow/switch_case_edge_group.py`,
`$AE` = `python/packages/core/agent_framework/_workflows/_agent_executor.py` (both
passed as absolute paths).

**L1** `handshake infer --producer store_email --consumer spam_detection_agent --source $AE:run --name l1_store_to_spam_agent`
```
$AE:run reads no fields from its input.
  line 389: 'request' is used as a whole; the inferred contract may be incomplete
  line 391: 'request' is used as a whole; the inferred contract may be incomplete
exit=2
```
Found 0. Really read: `messages` (389), `should_respond` (391). Miss: attribute access
on a dataclass. Note: `infer` skipped `self` and picked `request` correctly.

**L2** `handshake infer --producer spam_detection_agent --consumer to_detection_result --source $SRC:to_detection_result --name l2_spam_agent_to_detection_result`
```
$SRC:to_detection_result reads no fields from its input.
  line 115: 'response' is used as a whole; the inferred contract may be incomplete
exit=2
```
Found 0. Really read: `agent_response.text` (115), and inside that JSON text
`spam_decision` and `reason` (117, through `parsed.`). Misses: attribute chain on the
framework object; the JSON string is given to `DetectionResultAgent.model_validate_json`
(a helper), and the fields are then read as Pydantic attributes.

**L3** `handshake infer --producer to_detection_result --consumer submit_to_email_assistant --source $SRC:submit_to_email_assistant --name l3_detection_to_submit`
```
$SRC:submit_to_email_assistant reads no fields from its input.
  line 123: 'detection' is used as a whole; the inferred contract may be incomplete
  line 127: 'detection' is used as a whole; the inferred contract may be incomplete
exit=2
```
Found 0. Really read: `spam_decision` (123), `email_id` (127, inside an f-string key).
Miss: attribute access on a dataclass.

**L4** `handshake infer --producer to_detection_result --consumer handle_spam --source $SRC:handle_spam --name l4_detection_to_handle_spam`
```
$SRC:handle_spam reads no fields from its input.
  line 143: 'detection' is used as a whole; the inferred contract may be incomplete
  line 144: 'detection' is used as a whole; the inferred contract may be incomplete
exit=2
```
Found 0. Really read: `spam_decision` (143), `reason` (144, in an f-string). Miss:
attribute access on a dataclass.

**L5** `handshake infer --producer to_detection_result --consumer handle_uncertain --source $SRC:handle_uncertain --name l5_detection_to_handle_uncertain`
```
$SRC:handle_uncertain reads no fields from its input.
  line 152: 'detection' is used as a whole; the inferred contract may be incomplete
  line 153: 'detection' is used as a whole; the inferred contract may be incomplete
  line 155: 'detection' is used as a whole; the inferred contract may be incomplete
exit=2
```
Found 0. Really read: `spam_decision` (152), `email_id` (153), `reason` (155). Miss:
attribute access on a dataclass.

**L6** `handshake infer --producer submit_to_email_assistant --consumer email_assistant_agent --source $AE:run --name l6_submit_to_assistant_agent`
Same output as L1 (lines 389, 391, exit=2). Found 0 of 2 (`messages`,
`should_respond`). Miss: attribute access on a dataclass.

**L7** `handshake infer --producer email_assistant_agent --consumer finalize_and_send --source $SRC:finalize_and_send --name l7_assistant_agent_to_finalize`
```
$SRC:finalize_and_send reads no fields from its input.
  line 136: 'response' is used as a whole; the inferred contract may be incomplete
exit=2
```
Found 0. Really read: `agent_response.text` (136), `response` inside the JSON (137).
Misses: attribute chain, JSON string given to `EmailResponse.model_validate_json`,
Pydantic attribute.

**L8, L9, L10** (shared state). No separate command is possible. The consumers are the
same functions as L2, L3, L5, and the state is read from the second parameter `ctx`
(`ctx.get_state(...)`, lines 116, 127, 153). `infer` has no option to choose the
parameter, and its output for L2, L3, L5 says nothing about `ctx`. Really read:
`current_email_id` (116), `Email.email_content` (129), `Email.email_content` (155,
through `getattr`). Found 0 of 3.

**Extra: switch-case predicate** `handshake infer --producer to_detection_result --consumer switch_case_condition --source $SRC:condition --name x_switch_case_condition`
```
$SRC:condition reads no fields from its input.
  line 94: 'message' is used as a whole; the inferred contract may be incomplete
  line 94: 'message' is used as a whole; the inferred contract may be incomplete
exit=2
```
The nested function inside `get_case` was found. It reads `spam_decision` (94) and
also passes `message` to `isinstance`. Not counted in the totals.

No spec was written by any run (exit 2 each time). `handshake test` then gave
`Error loading specs: Specs directory not found: handshake/specs`, exit 2. I wrote one
spec by hand, `handshake/specs/detection-to-handle-uncertain.yaml` (L5:
`spam_decision` enum, `reason`, `email_id`, all required). `handshake test` then gave
`3 passed (total: 3)`, exit 0. `handshake infer --check` gave `No inferred specs
found, nothing to check.`, exit 0.

The WARN text "'detection' is used as a whole" is shown for `detection.spam_decision`.
The code reads one attribute there, it does not use the object as a whole. The
message is misleading for this case, but it did not break the run.

Fields found / total read: 0 / 19
(L1 2, L2 3, L3 2, L4 2, L5 3, L6 2, L7 2, L8 1, L9 1, L10 1.)

## 4. Unsupported read forms

| form | example | how often in the example |
|---|---|---|
| Attribute access on a dataclass message parameter | `detection.email_id` line 127 | 7 reads (123, 127, 143, 144, 152, 153, 155); plus 1 in the predicate (94) and 2 in `AgentExecutor.run` (`_agent_executor.py:389, 391`) |
| Attribute chain on a framework response object | `response.agent_response.text` line 115 | 2 (115, 136) |
| JSON string parsed by a Pydantic helper, then Pydantic attributes | `DetectionResultAgent.model_validate_json(...)` line 115, `parsed.reason` line 117 | 2 helper calls (115, 136), 3 attribute reads (117 x2, 137) |
| Shared workflow state via `ctx.get_state` (second parameter, not the message) | `ctx.get_state(CURRENT_EMAIL_ID_KEY)` line 116 | 3 gets (116, 127, 153), then 2 attribute reads on the result (129, 155) |
| `getattr` with a string name and a default | `getattr(email, 'email_content', '')` line 155 | 1 |
| Value used in an f-string (with attribute access) | `f"Email marked as spam: {detection.reason}"` line 144 | 4 (127, 137, 144, 155) |
| Free chat text to an LLM agent | `Message("user", contents=[email.email_content])` line 129 | 2 (108, 129) |

No dict subscript, `.get()` or `in` read occurs in this example, so no read here is in
a form `infer` supports.

## 5. Silent-breakage risk

Yes, one. `handle_uncertain` (lines 152-156) reads the email from shared state with
defaults at two levels:

```python
email: Email | None = ctx.get_state(f"{EMAIL_STATE_PREFIX}{detection.email_id}")
await ctx.yield_output(
    f"Email marked as uncertain: {detection.reason}. Email content: {getattr(email, 'email_content', '')}"
)
```

`ctx.get_state` returns `None` when the key is missing
(`python/packages/core/agent_framework/_workflows/_workflow_context.py:437-439`), and
`getattr(..., '')` turns a missing object or a missing attribute into an empty string.
The producer of that state is `store_email` (lines 102-104), and the field name comes
from the dataclass `Email` (lines 83-86). If `Email.email_content` is renamed, or
`email_id` does not match a stored key (for example `ctx.get_state` at line 116
returns `None`), the NotSpam branch fails loudly (`email.email_content` at line 129
raises `AttributeError`), but the Uncertain branch, which is the one meant for human
review, silently prints "Email content: " with nothing after it. A type checker does
not catch the rename, because the attribute name is a string literal. `handshake`
cannot see this either: it is a shared-state read through `getattr` on the `ctx`
parameter.

## 6. Setup

8 steps:
1. Read the sample and the framework types `AgentExecutorRequest` /
   `AgentExecutorResponse` (`_agent_executor.py:206-233`) to decide the snapshot shapes.
2. Create a work directory and `handshake.yaml`.
3. Write a small script that builds the snapshots from the three resource emails.
4. Run it (11 snapshot files, 5 agent ids).
5. Run `handshake infer` 8 times (7 links plus the predicate).
6. Run `handshake test` (fails: no specs directory, because every `infer` exited 2).
7. Write one spec by hand.
8. Run `handshake test` again (passes) and `handshake infer --check`.

Awkward:
- Choosing a snapshot shape for `AgentExecutorResponse` is a judgement call. The real
  object holds `AgentResponse` and `Message` objects, and the structured output is a
  JSON string inside `agent_response.text`. Even with full support for attribute
  access, the fields inside that string would stay hidden.
- No way to tell `infer` which parameter carries the data, so shared state on `ctx`
  cannot be tried at all.
- When `infer` finds no fields it writes nothing, so `handshake test` has nothing to
  run until a spec is written by hand.
- The WARN wording "used as a whole" for an attribute read (see section 3).
- My shell (zsh) read `$VAR:r` in `$AE:run` as a path modifier, so the first two
  commands got mangled paths. Quoting as `"${AE}:run"` fixed it. Not a tool problem.

## Tool bugs

None. No crash or traceback. Every run gave a clear message and a documented exit
code.

## Summary row

| Microsoft Agent Framework (switch_case_edge_group.py) | dataclass messages, Pydantic structured output as JSON text in a framework response, chat text in a dataclass request, shared workflow state | partly | 0/19 | attribute access on dataclass/Pydantic/framework objects; shared state on `ctx` | yes (`getattr(email, 'email_content', '')` on shared-state Email, line 155) |

- Typed links (Pydantic/TypedDict/dataclass/Zod): 5 (L2, L3, L4, L5, L7)
- Free-text links: 2 (L1, L6)
- Shared-state links: 3 (L8, L9, L10)
- Links where data is passed into helper functions: 4 (L1, L6: `request.messages`
  into `self._cache.extend`; L2, L7: JSON text into `model_validate_json`)
