# CrewAI flow template

Run on 2026-10-17 with agent-handshake 0.9.0 from PyPI. The snapshots and specs were written by hand in a local work directory and are not committed; each one's source is given below.

Repository: crewAIInc/crewAI. Commit: cf9f08a. Example path: `lib/cli/src/crewai_cli/templates/flow/` (main example) and `lib/cli/src/crewai_cli/templates/crew/` (second example). Framework: CrewAI. Language: Python (plus YAML config for agents and tasks).

This is the project that `crewai create flow` writes for every new flow project. `main.py` defines `ContentFlow`, a `Flow` with a Pydantic state `ContentState` (`topic`, `outline`, `draft`, `final_post`). The start step `plan_content` sets the topic, from an optional trigger payload or the fixed value "AI Agents". The step `generate_content` runs `ContentCrew` with `inputs={"topic": ...}`. The crew has three agents (planner, writer, editor) and three tasks that run in order. Each task gets the text output of the tasks before it as context. The step `save_content` writes the crew's final text to `output/post.md`. The second example, the `crew` template, is a plain two-agent crew (researcher, reporting analyst) started with an inputs dict. All template files contain `{{placeholders}}`. In the Python files these make the code invalid until `crewai create` fills them in.

## 1. How the agents are linked

Flow template (paths relative to `lib/cli/src/crewai_cli/templates/flow/`, framework code relative to `lib/crewai/src/crewai/`):

| link | producer | consumer | data form | file:line |
|---|---|---|---|---|
| L1 | trigger payload (external JSON from argv or the platform) | `plan_content` | dict parameter `crewai_trigger_payload`, read with `.get("topic", "AI Agents")` | main.py:21, main.py:25; payload made at main.py:75, main.py:82; injected by flow/runtime/__init__.py:2872-2882 |
| L2 | `plan_content` | `generate_content` | shared Pydantic flow state, `self.state.topic` | written main.py:25, main.py:28; read main.py:34, main.py:38 |
| L3 | `generate_content` | planner, writer, editor (task and agent prompts) | dict `inputs={"topic": ...}` rendered into `{topic}` prompt placeholders | main.py:38; crews/content_crew/config/agents.yaml:5, :15, :27; tasks.yaml:3, :20, :36; rendered by task.py:1087 (`interpolate_only`) |
| L4 | planner (`planning_task`) | writer (`writing_task`) | free text, implicit sequential context (no `context:` key, so all earlier raw outputs are joined) | tasks.yaml:1-16, tasks.yaml:20 ("Using the outline provided"); crew.py:1879-1886; utilities/formatter.py:26 |
| L5 | writer (`writing_task`), and planner | editor (`editing_task`) | free text, same implicit context (outline and draft joined with a divider) | tasks.yaml:34-50; crew.py:1884; utilities/formatter.py:26 |
| L6 | `ContentCrew` (editor output) | `generate_content` | Pydantic model attribute `CrewOutput.raw` | main.py:35-42; crews/crew_output.py:17 |
| L7 | `generate_content` | `save_content` | shared Pydantic flow state, `self.state.final_post` | written main.py:42; read main.py:50 |

Crew template (paths relative to `lib/cli/src/crewai_cli/templates/crew/`):

| link | producer | consumer | data form | file:line |
|---|---|---|---|---|
| C1 | `run()` / `run_with_trigger()` inputs | researcher, reporting analyst (prompts) | dict `{topic, current_year}` (plus `crewai_trigger_payload` in trigger mode) rendered into prompt placeholders; the payload is appended whole to the first task's description | main.py:16-22, main.py:80-87; config/agents.yaml:3, :5, :8, :13, :15; config/tasks.yaml:3, :5, :7; framework task.py:985-990, crew.py:2510-2522 |
| C2 | researcher (`research_task`) | reporting analyst (`reporting_task`) | free text, implicit sequential context | config/tasks.yaml:12 ("Review the context you got"); crew.py:1879-1886 |

Count: 7 links in the flow template, 2 in the crew template, 9 in total. Only L1 has a consumer function that takes the producer's data as a parameter.

## 2. Does the producer -> consumer model fit?

Partly. The flow and the crews do have clear producers and consumers, and data moves in one direction. But only one link (L1) matches the tool's model of "a function that takes the producer's output dict as a parameter". The flow steps take no parameters and read a shared Pydantic state (`self.state`). The agents never see structured data at all: they get a dict rendered into prompt text, and the output of one task reaches the next as joined free text. That handover happens inside the framework (crew.py:1879-1886), not in the project's code. The one result read from the crew is an attribute on a Pydantic model (`result.raw`, main.py:42).

## 3. What infer found

Setup note: `main.py` is not valid Python as shipped (`from {{folder_name}}.crews...` at main.py:8). The first run failed with a clean error:

```
$ handshake infer --producer trigger --consumer plan_content --source <repo>/lib/cli/src/crewai_cli/templates/flow/main.py:plan_content --out -
Error: Cannot parse .../templates/flow/main.py: invalid syntax (main.py, line 8)
exit=2
```

I made rendered copies in the work directory with `sed`, the same text replacement that `create_flow.py:84` does (`{{folder_name}}` -> `my_flow`; for the crew template `{{crew_name}}` -> `MyCrew`). Only those import and class lines changed. All runs below use `rendered/...`.

Snapshots (all hand-written, under `handshake/snapshots/`):
- `trigger/with_topic_001.json`: output `{"topic": "AI Agents"}`. The key comes from main.py:25; the value is the code's own default.
- `plan_content/default_topic_001.json`: the `ContentState` dump after `plan_content` with no payload (main.py:11-15, main.py:28).
- `content_crew/ai_agents_001.json`, `generate_content/ai_agents_001.json`: `CrewOutput` fields (crew_output.py:17-26) and the state after main.py:42. The `raw` text is a short stand-in for the model's markdown post; any string is possible there.
- `planner/ai_agents_001.json`: `TaskOutput` fields (tasks/task_output.py:30-44); `description` and `expected_output` come from tasks.yaml:3, :13-15; `raw` is a stand-in outline.
- `generate_content_inputs/ai_agents_001.json`: `{"topic": "AI Agents"}` (main.py:38).
- `crew_run_inputs/run_001.json`: `{"topic": "AI LLMs", "current_year": "2026"}` (crew main.py:16-19). `crew_run_inputs/trigger_001.json`: `{"crewai_trigger_payload": {"topic": "AI LLMs"}, "topic": "", "current_year": ""}` (crew main.py:80-84; the payload's content is up to the caller).

**L1** `handshake infer --producer trigger --consumer plan_content --source rendered/flow/main.py:plan_content`
- Found: `topic` (required, read at line 25). Exit 0. `handshake test`: PASS.
- WARN: `line 24: 'crewai_trigger_payload' is used as a whole` and `line 26: ... used as a whole`. Line 24 is the truth test `if crewai_trigger_payload:`, line 26 is an f-string `print`. Neither reads a field, but both set `reads_unknown_keys: true`.
- Note: the code reads `topic` with `.get(..., "AI Agents")`, so for the consumer it is optional. The spec says `required` because the only snapshot has it. A probe with a second snapshot without `topic` made it optional; a probe with only that snapshot gave `FAIL: 'topic' is read by plan_content (line 25) but trigger never sent it`, exit 1. So the spec follows the snapshots, not the default in the code.
- Misses: none. 1 / 1.

**L2** `handshake infer --producer plan_content --consumer generate_content --source rendered/flow/main.py:generate_content`
- `Error: Function 'generate_content' in rendered/flow/main.py takes no input parameter`, exit 2. `ContentFlow.generate_content` as the name gives `not found`.
- Miss: `topic` (attribute on `self.state`, main.py:34, :38). 0 / 1.

**L3** No project function takes the inputs dict. Closest function: the framework method that renders it, `handshake infer --producer generate_content_inputs --consumer planning_task --source lib/crewai/src/crewai/task.py:interpolate_inputs_and_add_conversation_history`.
- First run: 4 WARN lines (`'inputs' is used as a whole` at task.py lines 1083, 1088, 1104, 1112, where `inputs` goes to `interpolate_only`), then `FAIL: 'crew_chat_messages' is read by planning_task (line 1117, 1122) but generate_content_inputs never sent it`, exit 1. With `--allow-missing crew_chat_messages`: spec written with 1 field, `crew_chat_messages`, optional. `handshake test`: PASS.
- `crew_chat_messages` is a framework field, not something the template reads. `handshake infer --check` then fails on this new spec (see Tool bugs).
- Miss: `topic` (prompt placeholder in YAML, reached through the helper `interpolate_only`). 0 / 1.

**L4, L5** No project function. `rendered/flow/crews/content_crew/content_crew.py:writing_task` gives `takes no input parameter`, exit 2. Closest framework functions:
- `--source lib/crewai/src/crewai/utilities/formatter.py:aggregate_raw_outputs_from_task_outputs`: `reads no fields from its input. line 26: 'task_outputs' is used as a whole`, exit 2. (The input is a list; `.raw` is read on each item.)
- `--source lib/crewai/src/crewai/crew.py:_get_context`: the tool takes the first parameter (`task`), not `task_outputs`; `reads no fields`, 3 WARN lines (crew.py lines 1880, 1885, 1886), exit 2.
- Misses: `raw` of the planner output (L4), `raw` of the earlier outputs (L5). 0 / 2.

**L6** `handshake infer --producer content_crew --consumer generate_content --source rendered/flow/main.py:generate_content`: `takes no input parameter`, exit 2. Miss: `raw` (attribute on the returned `CrewOutput`, main.py:42). 0 / 1.

**L7** `handshake infer --producer generate_content --consumer save_content --source rendered/flow/main.py:save_content`: `takes no input parameter`, exit 2. Miss: `final_post` (attribute on `self.state`, main.py:50). 0 / 1.

**C1** `handshake infer --producer crew_run_inputs --consumer research_task --source rendered/crew/main.py:run`: `takes no input parameter`, exit 2. With the framework method `task.py:interpolate_inputs_and_add_conversation_history` and `--allow-missing crew_chat_messages`: same result as L3, 1 framework field (`crew_chat_messages`), 4 WARN lines. `handshake test`: PASS for both snapshots, including the one where `topic` and `current_year` are `""`. Misses: `topic`, `current_year` (prompt placeholders through `interpolate_only`), `crewai_trigger_payload` (read in `Task.prompt` as `crew._inputs.get(...)`, task.py:988, a different function reached through attributes). 0 / 3.

**C2** No project function; same as L4 (free text joined in the framework). Miss: `raw`. 0 / 1.

Final `handshake test`: 4 passed, exit 0. Final `handshake infer --check`: exit 1 (the two `crew_chat_messages` specs, see Tool bugs; `trigger-to-plan_content` is OK).

Fields found / total read: 1 / 11 (flow template 1 / 7, crew template 0 / 4). The one framework field found (`crew_chat_messages`) is not counted, since the template does not read it.

## 4. Unsupported read forms

| form | example | how often in the example |
|---|---|---|
| Attribute on shared Pydantic flow state in a step with no parameter | main.py:38 `self.state.topic`, main.py:50 `self.state.final_post` | 4 reads (main.py:30, :34, :38, :50) on 2 links (L2, L7) |
| Attribute on a returned Pydantic model | main.py:42 `result.raw` | 1 (L6) |
| Prompt placeholder in YAML, filled from an inputs dict | flow tasks.yaml:3 `{topic}`; crew tasks.yaml:5 `{current_year}` | flow 6 (agents.yaml 3, tasks.yaml 3); crew 8 (agents.yaml 5, tasks.yaml 3) |
| Inputs dict passed to a helper (`interpolate_only`) | task.py:1088, :1104, :1112 | every kickoff (L3, C1) |
| Implicit free-text context between sequential tasks, joined in the framework; list items read with `.raw` | crew.py:1884, utilities/formatter.py:26 | 3 links (L4, L5, C2) |
| Value read through an attribute chain in another function | task.py:988 `crew._inputs.get("crewai_trigger_payload")` | 1 (C1, trigger mode) |
| Template placeholder that makes the Python file unparsable | flow main.py:8, crew main.py:7, crew crew.py:7 | 3 files; needs rendering before `infer` |
| Whole-object use that is not a field read but still gives a WARN | main.py:24 truth test, main.py:26 f-string print | 2 WARN lines on L1 |

## 5. Silent-breakage risk

Yes, one real case, plus one by design in the crew template.

1. Flow template, main.py:25: `self.state.topic = crewai_trigger_payload.get("topic", "AI Agents")`. The producer is any JSON the caller sends (main.py:75 `json.loads(sys.argv[1])`, or the platform trigger). Nothing guarantees a `topic` key. If the trigger sends the topic under another name (for example a renamed field), the flow does not fail: it writes and saves a full post about "AI Agents" (main.py:38, :42, :50). The spec from `infer` marks `topic` as required, so `handshake test` would catch a recorded trigger snapshot without `topic`.
2. Crew template, main.py:80-84: `run_with_trigger` passes `"topic": ""` and `"current_year": ""`. `interpolate_only` raises only for a missing key (utilities/string_utils.py:138-141), not for an empty value, so the prompts become "Conduct a thorough research about " and the role " Senior Data Researcher" (config/tasks.yaml:3, config/agents.yaml:3). The payload is appended to the first task's description (task.py:985-990, crew.py:2510-2522), so the model may still use it. `handshake test` passes this snapshot, because `""` is a valid string.

Smaller notes: `ContentState.outline` and `ContentState.draft` (main.py:13-14) are declared with default `""` and never written by any step; a future step that reads them gets `""` with no error. `CrewOutput.raw` defaults to `""` (crews/crew_output.py:17), so an empty crew result would save an empty `output/post.md` without an error.

## 6. Setup

9 steps:
1. Create a work directory and `handshake.yaml`.
2. Write the trigger snapshot.
3. Run `infer` on the template `main.py`: parse error (main.py:8).
4. Render copies of the template files with `sed`, as `create_flow.py:84` does.
5. Run `infer` for L1, then `handshake test`.
6. Write state snapshots for `plan_content`, `content_crew`, `generate_content`; every `infer` on the flow steps failed with "takes no input parameter".
7. Find the framework functions that do the handover (task.py, crew.py, formatter.py) and write `planner` and inputs snapshots for them.
8. Rerun with `--allow-missing crew_chat_messages` after the first FAIL.
9. Run `handshake test` and `handshake infer --check`.

Awkward:
- The template is not valid Python before `crewai create` fills it in.
- The natural "agents" (planner, writer, editor) have no code at all, only YAML. The only functions are flow steps, and they read `self.state`, so "producer id" and "consumer id" had to be made up (`plan_content`, `generate_content_inputs`).
- A snapshot of shared state is a dump of the whole state model, written by hand.
- There is no way to choose which parameter is the input (`_get_context(task, task_outputs)` took `task`).
- To say anything about the prompt links I had to point `infer` at framework code, which brought in a framework-only field (`crew_chat_messages`) and a FAIL.
- `.get("topic", default)` became `required` in the spec, so the spec is stricter than the consumer.

## Tool bugs

1. A spec written by `handshake infer --allow-missing FIELD` fails `handshake infer --check` right away when the code reads FIELD with `data["FIELD"]`, and the "Regenerate" command that `--check` prints fails too (it drops `--allow-missing`). No spec can pass both commands. In this run it hit `task.py:interpolate_inputs_and_add_conversation_history`, where the `[]` read at line 1122 is inside `if inputs.get("crew_chat_messages"):` (line 1117), so the read is guarded and the field is optional in fact.

   Minimal repro:
   ```
   $ cat consumer.py
   def b(data):
       return data["x"]
   $ cat handshake/snapshots/a/s_001.json
   {"schema_version": 1, "agent_id": "a", "scenario": "s", "input": {}, "output": {"y": 1}}
   $ handshake infer --producer a --consumer b --source consumer.py:b --allow-missing x --force
   WARN: 'x' is read by b (line 2) but a never sent it in any snapshot; allowed by --allow-missing
   Wrote handshake/specs/a-to-b.yaml (1 field(s) from consumer.py:b)
   exit=0
   $ handshake infer --check
   FAIL a-to-b (consumer.py:b)
       b reads 'x' with [] (line 2), but the spec makes it optional
       Regenerate: handshake infer --producer a --consumer b --source consumer.py:b --out handshake/specs/a-to-b.yaml --force
   exit=1
   $ handshake infer --producer a --consumer b --source consumer.py:b --out handshake/specs/a-to-b.yaml --force
   FAIL: 'x' is read by b (line 2) but a never sent it in any snapshot
   exit=1
   ```
   The guarded form `if data.get("x"): return data["x"]` gives the same `--check` FAIL (`reads 'x' with [] (line 2, 3)`). With `return data.get("x")` only, `--check` is OK.

## Summary row

| CrewAI flow template (+ crew template) | dict param, Pydantic shared flow state, Pydantic model attribute, dict into prompt placeholders, free-text task context | partly | 1/11 | flow steps take no parameter and read `self.state`; agents exchange free text and prompt placeholders inside the framework | yes (trigger `.get("topic", "AI Agents")` silently falls back, main.py:25) |

Typed links (Pydantic/TypedDict/dataclass/Zod): 3 (L2, L6, L7).
Free-text links: 3 (L4, L5, C2).
Shared-state links: 2 (L2, L7).
Links where data is passed into helper functions: 5 (L3, C1 into `interpolate_only`; L4, L5, C2 into `aggregate_raw_outputs_from_task_outputs`), all inside the framework.
