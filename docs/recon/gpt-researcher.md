# GPT Researcher (multi_agents)

Run on 2026-10-17 with agent-handshake 0.9.0 from PyPI. The snapshots and specs were written by hand in a local work directory and are not committed; each one's source is given below.

- Repository: assafelovic/gpt-researcher
- Commit: 3582a68
- Example path: `multi_agents/` (agents in `multi_agents/agents/`, state in `multi_agents/memory/`)
- Framework: LangGraph
- Language: Python

The example writes a research report from one query in `multi_agents/task.json`. An outer
LangGraph graph (`multi_agents/agents/orchestrator.py:65-105`) runs these nodes: a browser
(initial research), a planner (section outline), a human review of the plan, a parallel
researcher, a writer (introduction, conclusion, sources), a fact checker, a visualizer
(Mermaid diagram) and a publisher (markdown/PDF/DOCX). The parallel researcher
(`multi_agents/agents/editor.py:57-82`) starts one inner graph per section
(`editor.py:131-149`): depth researcher, then a reviewer/reviser loop. There are three loops:
human -> planner, reviewer <-> reviser, fact checker -> writer. All data travels in two
TypedDict states, `ResearchState` (`multi_agents/memory/research.py:5-23`) and `DraftState`
(`multi_agents/memory/draft.py:5-12`). Every node takes the whole state as a plain `dict`,
reads it with `.get(...)` and returns a partial dict that LangGraph merges back.

## 1. How the agents are linked

Producer -> consumer means: the producer node returns the field, the consumer node reads it
from the shared state later. File:line is "where written -> where read".

| link | producer | consumer | data form | file:line |
|---|---|---|---|---|
| L1 | browser (`ResearchAgent.run_initial_research`) | planner (`EditorAgent.plan_research`) | shared state: `initial_research` (markdown text), `task` (re-emitted) | `agents/researcher.py:50` -> `agents/editor.py:34-35` |
| L2 | human (`HumanAgent.review_plan`) | planner, plan router | shared state: `human_feedback` (free text), `plan_revision_count` | `agents/human.py:58-61` -> `agents/editor.py:37`, `agents/plan_review.py:9,15` |
| L3 | planner | human | shared state: `sections` (list of str) | `agents/editor.py:54` -> `agents/human.py:14` |
| L4 | planner | parallel researcher (`EditorAgent.run_parallel_research`) | shared state: `sections`, `title` | `agents/editor.py:52-54` -> `agents/editor.py:68-69` |
| L5 | parallel researcher | writer (`WriterAgent.run`) | shared state: `research_data` (list of `{section: markdown}`) | `agents/editor.py:82` -> `agents/writer.py:34` (in helper) |
| L6 | planner | writer | shared state: `title` | `agents/editor.py:52` -> `agents/writer.py:24,33` (in helpers) |
| L7 | fact checker (`FactCheckerAgent.run`) | writer, fact router | shared state: `fact_check_notes` (free text), `fact_check_revision_count` | `agents/fact_checker.py:61-65` -> `agents/writer.py:39`, `agents/fact_review.py:9,15` |
| L8 | writer | fact checker | shared state: `introduction`, `conclusion` (LLM JSON spread into state) | `agents/writer.py:146` -> `agents/fact_checker.py:14-15` (in helper) |
| L9 | parallel researcher | fact checker | shared state: `research_data` | `agents/editor.py:82` -> `agents/fact_checker.py:16` (in helper) |
| L10 | parallel researcher | visualizer (`VisualizerAgent.run`) | shared state: `research_data` | `agents/editor.py:82` -> `agents/visualizer.py:14` (in helper) |
| L11 | writer | publisher (`PublisherAgent.run`) | shared state: `introduction`, `table_of_contents`, `conclusion`, `sources`, `headers` (nested dict) | `agents/writer.py:146` -> `agents/publisher.py:37-66` (in helper) |
| L12 | visualizer | publisher | shared state: `diagrams` (list of markdown text) | `agents/visualizer.py:56` -> `agents/publisher.py:46` (in helper) |
| L13 | parallel researcher | publisher | shared state: `research_data` | `agents/editor.py:82` -> `agents/publisher.py:24` (in helper) |
| L14 | planner | publisher | shared state: `date` | `agents/editor.py:53` -> `agents/publisher.py:55` (in helper) |
| L15 | parallel researcher (`_create_task_input`) | depth researcher (`ResearchAgent.run_depth_research`) | subgraph input dict -> `DraftState`: `task`, `topic`, `sibling_sections` (also `title`, `headers`, which `DraftState` does not declare) | `agents/editor.py:184-192` -> `agents/researcher.py:54-65` |
| L16 | depth researcher | reviewer (`ReviewerAgent.run`) | shared state: `draft` (`{topic: markdown}`) | `agents/researcher.py:66` -> `agents/reviewer.py:40` (in helper, inside an f-string) |
| L17 | reviewer | reviser (`ReviserAgent.run`), draft router | shared state: `review` (free text), `draft_revision_count` | `agents/reviewer.py:84-86` -> `agents/reviser.py:27` (in helper), `agents/draft_review.py:17,23` |
| L18 | reviser | reviewer | shared state: `draft`, `revision_notes` (LLM JSON) | `agents/reviser.py:71-74` -> `agents/reviewer.py:26,40` (in helper) |
| L19 | depth researcher | reviser | shared state: `draft` | `agents/researcher.py:66` -> `agents/reviser.py:29` (in helper) |
| L20 | inner graph (final `DraftState`) | parallel researcher | subgraph result dict: `draft`, read in a list comprehension | `agents/reviser.py:72` / `agents/researcher.py:66` -> `agents/editor.py:79` |

Count: 20 agent -> agent links (14 in the outer graph, 6 in or around the inner graph).
On top of these, the user's `task` dict (`multi_agents/task.json`, passed at
`agents/orchestrator.py:171`) is read by every node. The browser re-emits it
(`researcher.py:50`) and the parallel researcher copies it into the inner graph
(`editor.py:185`). Its reads are counted below, but it is not counted as a link.

## 2. Does the producer -> consumer model fit?

Partly.

- What fits: every node returns a small, clear dict (`return {...}` at the end of each
  `run`). That is a good producer snapshot. Consumers read with `state.get("key")`, the
  form `infer` handles best.
- What does not fit: a consumer does not read one producer's output. It reads the merged
  state, written by 2 to 5 producers plus the user task. The publisher reads fields from
  the writer, visualizer, parallel researcher, planner and the task. With one producer per
  spec, every infer run for these nodes failed (`FAIL ... never sent it in any snapshot`)
  until each field of the other producers was passed with `--allow-missing`. Those fields
  then become optional in the spec, so the spec stops checking them.
- The loops make it worse: the reviewer reads `draft` from the depth researcher in round 1
  and from the reviser in later rounds; the writer reads `fact_check_notes` only after a
  fact-check round. The same consumer needs a spec per producer, and each spec repeats the
  consumer's reads.
- Most reads are not in the node function. 7 of the 11 agent nodes hand the whole state
  to a helper method (`review_draft`, `revise_draft`, `write_sections`, `check_facts`,
  `generate_visualizations`, `generate_layout`, ...). `infer` warns, but the user has to
  find and point at each helper.

## 3. What infer found

Snapshots: 14 hand-written files for 11 producers, in
`handshake/snapshots/<producer>/`, generated by a small local script.
Each output copies the producer's `return` statement; LLM-made values follow the JSON shape
the prompt asks for (planner `editor.py:118-121`, writer `writer.py:6-13`, reviser
`reviser.py:5-12`); `task` is `multi_agents/task.json`. Two-path scenarios (`feedback_given`,
`needs_revision`, `issues_found`) use the non-None branch of `human.py:52-55`,
`reviewer.py:85-86`, `fact_checker.py:62-65`.

All commands were run from the local work directory as
`handshake infer --producer P --consumer C --source <repo>/multi_agents/<file>:<function>`.
"Read" is my count of field paths the consumer reads, including `task.*` subfields and
reads inside helpers. "Node fn" is what infer found on the function LangGraph calls (for
the routers, the plain `route_*` function the orchestrator wrapper calls).

| consumer (links) | `--source` | first run | `--allow-missing` needed | found by node fn / read | found with helpers / read |
|---|---|---|---|---|---|
| planner (L1, L2) | `agents/editor.py:plan_research` | FAIL `human_feedback` (exit 1) | `human_feedback` | 6 / 6 | 6 / 6 |
| human (L3) | `agents/human.py:review_plan` | FAIL `task`, `plan_revision_count` | both | 4 / 4 | 4 / 4 |
| plan router (L2) | `agents/plan_review.py:route_human_feedback` | OK | none | 2 / 2 | 2 / 2 |
| parallel researcher (L4) | `agents/editor.py:run_parallel_research` | OK, WARN line 75 | none | 2 / 3 | 3 / 3 (`_create_task_input`, needs `--allow-missing task`) |
| depth researcher (L15) | `agents/researcher.py:run_depth_research` | FAIL `task.source` | `task.source` | 6 / 6 | 6 / 6 |
| reviewer (L16, L18) | `agents/reviewer.py:run` | FAIL `task`, `draft_revision_count`; WARN line 81 | both | 5 / 8 | 7 / 8 (`review_draft`) |
| draft router (L17) | `agents/editor.py:_route_draft_review` + `agents/draft_review.py:route_draft_review` | FAIL `task`, WARN line 162 / OK | `task` | 3 / 4 | 3 / 4 |
| reviser (L17, L19) | `agents/reviser.py:run` | FAIL `task`; WARN line 56 | `task` | 2 / 5 | 5 / 5 (`revise_draft`) |
| parallel researcher, subgraph result (L20) | not possible: `result` is a list item from `asyncio.gather`, not a parameter (`editor.py:78-80`) | - | - | 0 / 1 | 0 / 1 |
| writer (L5, L6, L7) | `agents/writer.py:run` | FAIL `task`; WARN lines 112, 128 | `task` | 3 / 8 | 8 / 8 (`write_sections`, `get_headers`) |
| fact checker (L8, L9) | `agents/fact_checker.py:run` | FAIL `fact_check_revision_count`; WARN line 45 | that field | 1 / 6 | 6 / 6 (`check_facts`) |
| fact router (L7) | `agents/fact_review.py:route_fact_check` | OK | none | 2 / 2 | 2 / 2 |
| visualizer (L10) | `agents/visualizer.py:run` | exit 2: "reads no fields from its input", WARN line 41, no spec | - | 0 / 3 | 3 / 3 (`generate_visualizations`) |
| publisher (L11-L14) | `agents/publisher.py:run` | FAIL `task`; WARN line 88 | `task` | 2 / 19 | 10 / 19 (`generate_layout`) |

The helper runs needed their own `--allow-missing` lists, for example
`check_facts --allow-missing task --allow-missing research_data` and
`generate_layout --allow-missing research_data --allow-missing diagrams --allow-missing date`.

Misses on the node functions (39), by reason:
- Whole state passed to a helper (WARN shown, `reads_unknown_keys: true` set): 37.
  Publisher 17 (`publisher.py:88` -> `generate_layout`), writer 5, fact checker 5,
  reviewer 3, reviser 3, visualizer 3, parallel researcher 1 (`task`, `editor.py:185`).
- Local name bound with `x = state.get("k") or {}` (no WARN): 1, `task.max_draft_revisions`
  at `editor.py:158-160`.
- Subgraph result read as list items, not a parameter: 1, `result["draft"]` at `editor.py:79`.

Misses left even after pointing infer at every helper (12):
- `or {}` local name, silent: 8. `headers.title/date/introduction/table_of_contents/conclusion/references`
  at `publisher.py:41,54-68`; `task.model` at `reviewer.py:21,47`; `task.max_draft_revisions`
  at `editor.py:158-160`.
- Second-level helper that takes a sub-dict: 3. `task.publish_formats.pdf/docx/markdown`
  read in `write_report_by_formats` (`publisher.py:74-78`) through `publish_formats`.
- Subgraph result in a list comprehension: 1 (`editor.py:79`).

Good points seen: chained `.get("task").get("verbose")` (`writer.py:114`, `reviser.py:58`),
reads inside f-strings (`reviewer.py:40`, `publisher.py:55-66`) and reads through a plain
local name (`task = state.get("task")`) were all found. `handshake test` passed 31 of 31
checks; `handshake infer --check` exited 0. A copy of the project with one extra writer
snapshot where the LLM key `introduction` is renamed to `intro` (possible because
`writer.py:146` spreads unchecked LLM JSON) failed 2 checks
(`writer-to-fact_checker_check_facts`, `writer-to-publisher_generate_layout`), exit 1.

Fields found / total read: 38 / 77 on the node functions; 65 / 77 when infer is also pointed
at each helper by hand.

## 4. Unsupported read forms

| form | example | how often |
|---|---|---|
| Whole state passed to a helper method (WARN shown) | `review = await self.check_facts(research_state)` `agents/fact_checker.py:45` | 11 calls: `editor.py:75`, `reviewer.py:81`, `reviser.py:56`, `writer.py:112,128`, `fact_checker.py:45`, `visualizer.py:41`, `publisher.py:88`, `editor.py:162`, `orchestrator.py:119,133`; 37 of 39 misses |
| Local name bound with `or {}` (silent, no WARN, spec looks complete) | `headers = research_state.get("headers") or {}` then `headers.get('title')` `agents/publisher.py:41,54` | 3 places (`publisher.py:41`, `reviewer.py:21`, `editor.py:158`); 8 fields |
| A sub-dict passed to a second helper | `self.write_report_by_formats(layout, publish_formats)` -> `publish_formats.get("pdf")` `agents/publisher.py:18,74-78` | 1 place (also `revise_headers(task=...)` at `writer.py:141-143`, but its fields are read elsewhere too); 3 fields |
| Subgraph result read as list items | `result["draft"] for result in await asyncio.gather(*final_drafts)` `agents/editor.py:78-80` | 1 |
| Node whose own body reads nothing (all reads in a helper): infer exits 2 and writes no spec | `agents/visualizer.py:30-56` | 1 |
| Producer side: LLM JSON read in the producer before it reaches state (not an agent link, not counted) | `plan.get("sections")` `editor.py:54`, `revision.get("draft")` `reviser.py:72`, `{**research_layout_content}` `writer.py:146` | 3 |

## 5. Silent-breakage risk

Yes, two concrete cases.

1. Writer -> fact checker / publisher (L8, L11). `WriterAgent.run` returns
   `{**research_layout_content, "headers": headers}` (`agents/writer.py:146`), where
   `research_layout_content` is LLM output parsed by `parse_json_markdown(..., json_repair.loads)`
   (`agents/utils/llms.py:29-30`). No key is checked. The fact checker reads
   `research_state.get("introduction", "")` and `research_state.get("conclusion", "")`
   (`agents/fact_checker.py:14-15`). If the model names a key differently, the fact checker
   reviews an empty introduction and conclusion, can answer `None`, and the draft is
   accepted (`fact_checker.py:49-50`, `fact_review.py:9-10`). The publisher then prints the
   text `None` under the Introduction and Conclusion headers
   (`publisher.py:58,66`, `research_state.get('introduction')` in an f-string). The
   inferred spec catches this (both fields come out `required` because the writer snapshot
   always has them); the renamed-key snapshot failed `handshake test` as shown in section 3.
2. Writer -> publisher `headers` (L11). With `follow_guidelines: true`, the writer replaces
   its fixed headers with LLM JSON (`writer.py:141-144`). The task guideline asks for the
   report in Spanish (`task.json`), so translated keys are plausible. If `call_model`
   fails it returns `None` (`llms.py:34-36` has no return). The publisher hides both cases:
   `headers = research_state.get("headers") or {}` and `if not isinstance(headers, dict): headers = {}`
   (`publisher.py:41-43`), then `headers.get('title')`, `headers.get("introduction")`, ...
   (`publisher.py:54-68`), so the report gets `# None` and `## None` titles with no error.
   The inferred spec does not catch this: `infer` misses the six `headers.*` reads because
   of the `or {}` local name, so the spec only asks that `headers` exists.

Minor, producer side: `run_subtopic_research` swallows any error and returns
`{subtopic: None}` (`agents/researcher.py:36-39`); the publisher writes the text `None` as
that section (`publisher.py:28-31`).

## 6. Setup

8 steps:
1. Read the 20 Python files under `multi_agents/` and map the two graphs.
2. Create a work directory and `handshake.yaml` (`project_name: gpt-researcher-multi-agents`).
3. Write 14 snapshots for 11 producers by hand (a small script, from the `return`
   statements, prompt JSON shapes and `task.json`).
4. Run `handshake infer` once per consumer node (14 runs); 10 failed or exited 2.
5. Re-run each failed one with `--allow-missing` for every field written by another
   producer or by the user task (up to 3 flags per run).
6. Find each helper behind a WARN and run `infer` on it, again with its own
   `--allow-missing` list (8 more runs).
7. `handshake test` (31 passed) and `handshake infer --check` (exit 0).
8. Break check in a copy of the work directory (renamed writer key, 2 failures).

Awkward:
- Shared state does not have a single producer per field read. Choosing `--producer` is
  guesswork, and `--allow-missing` for the other producers' fields makes them optional,
  so the spec checks them less.
- The same consumer needs one spec per producer (writer from parallel researcher and from
  fact checker; reviewer from depth researcher and from reviser). Each repeats the same
  reads; I ended with 24 specs for 20 links.
- Helpers must be found by hand from the WARN line; spec names and consumer ids for
  helpers are made up by the user.
- A node that only calls a helper (`visualizer.py:run`) gets exit 2 and no spec, not a
  spec with `reads_unknown_keys: true`.
- `inferred_from` and the spec header store the absolute `--source` path given on the
  command line, so the spec is tied to this machine unless a relative path is used.

## Tool bugs

None that crashed or blocked the run. One silent gap that makes a spec look complete when
it is not (no WARN, no `reads_unknown_keys`, `infer --check` passes):

`x = data.get("k") or {}` followed by `x.get("sub")` does not record `k.sub`.
Repro: `c.py` contains

```python
def plain(state):
    task = state.get("task")
    return task.get("model")

def with_or(state):
    task = state.get("task") or {}
    return task.get("model")
```

and a snapshot of producer `p` with output `{"task": {"model": "m"}}`.
`handshake infer --producer p --consumer plain --source c.py:plain --out -` lists
`task` and `task.model`. The same command for `with_or` lists only `task`
(`task: required, read at line 6`), with no WARN. In the example this drops 8 field reads
(`publisher.py:41`, `reviewer.py:21`, `editor.py:158`).

## Summary row

| GPT Researcher (multi_agents) | shared LangGraph state (TypedDict, plain dict reads), subgraph input/result dict, free text and LLM JSON in state | partly | 38/77 (65/77 with helpers run by hand) | whole state passed to helper methods (37 of 39 misses); `x = d.get(k) or {}` local names missed silently | yes (writer spreads unchecked LLM JSON; fact checker reads `introduction`/`conclusion` with `""` default, publisher hides bad `headers` with `or {}`) |

- Typed links (Pydantic/TypedDict/dataclass/Zod): 20 (all go through the `ResearchState` / `DraftState` TypedDicts; nodes still take `dict` and use `.get`, inner values are untyped)
- Free-text links: 14 (L1, L2, L5, L7, L8, L9, L10, L11, L12, L13, L16, L17, L18, L19)
- Shared-state links: 20
- Links where data is passed into helper functions: 14 (L5-L14, L16-L19)
