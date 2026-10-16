# OpenAI Agents SDK (openai-agents-python)

Run on 2026-10-17 with agent-handshake 0.9.0 from PyPI. The snapshots and specs were written by hand in a local work directory and are not committed; each one's source is given below.

- Repository: openai/openai-agents-python
- Commit: 17d994b ("release: 0.24.0 (#5285)")
- Example: `examples/financial_research_agent/` (main). Second example: `examples/research_bot/`.
- Framework: OpenAI Agents SDK
- Language: Python

The financial example takes a research question. A planner agent returns a list
of web searches (`FinancialSearchPlan`). The manager runs one search agent per item
in parallel. Each search agent returns a `FinancialSearchSummary`. The manager wraps
each result, with the source URLs taken from the run items, into a
`FinancialSearchEvidence`. A writer agent gets this evidence as a JSON prompt. It can
call two analyst agents (fundamentals, risk) as tools and returns a
`FinancialReportData`. A verifier agent checks the report against the evidence and
returns a `VerificationResult`. If it fails, a clone of the writer with a revision
prompt rewrites the report once and the verifier checks it again. All agent outputs
are Pydantic models. A plain Python class (`FinancialResearchManager` in
`manager.py`) wires everything together. No agent reads another agent's output as a
dict. The data reaches the next LLM as an f-string or a JSON prompt.
`research_bot` is the same flow, smaller: planner, then search (free text, no output
type), then writer.

## 1. How the agents are linked

| link | producer | consumer | data form | file:line |
|---|---|---|---|---|
| L1 | planner_agent (`FinancialSearchPlan`) | search_agent | Pydantic. The manager reads `searches[].query` / `.reason` by attribute and puts them in an f-string prompt | `examples/financial_research_agent/manager.py:130,143,171,179-180` |
| L2 | search_agent (`FinancialSearchSummary`) | writer_agent | Pydantic. The manager reads `.summary` and wraps it in `FinancialSearchEvidence`, then sends `model_dump` as a JSON prompt | `manager.py:174,181,207,280-287` |
| L3 | search_agent (evidence wrapper) | verifier_agent | Pydantic. `model_dump` as a JSON prompt, and `sources[].url` read by attribute to build `allowed_source_urls` | `manager.py:262-271` |
| L4 | financials_agent (`AnalysisSummary`) | writer_agent | Agent called as a tool. `custom_output_extractor` turns `final_output.summary` into a free-text tool result | `manager.py:61-65,195-199` |
| L5 | risk_agent (`AnalysisSummary`) | writer_agent | Same as L4 | `manager.py:61-65,200-204` |
| L6 | writer_agent (`FinancialReportData`) | verifier_agent | Pydantic. The whole object goes in as `report.model_dump(mode="json")` inside a JSON prompt. This also runs again for the revised report | `manager.py:112,117,249-251,266` |
| L7 | verifier_agent (`VerificationResult`) | writer_agent (revision clone) | Pydantic. The manager branches on `.verified`, then puts `model_dump_json()` in an f-string prompt | `manager.py:113,118,121,232-236` |
| L8 | writer_agent (`FinancialReportData`) | writer_agent (revision clone) | Pydantic. The whole object goes in as `model_dump_json()` in an f-string prompt | `manager.py:116,233-235` |
| R1 | research_bot planner_agent (`WebSearchPlan`) | research_bot search_agent | Pydantic. `searches[].query` / `.reason` read by attribute, then an f-string prompt | `examples/research_bot/manager.py:60,71,95` |
| R2 | research_bot search_agent (no output type) | research_bot writer_agent | Free text. `str(result.final_output)`, then a Python list of strings in an f-string prompt | `examples/research_bot/manager.py:101,107` |

Count: 8 links in the financial example and 2 in research_bot, so 10 in total.
Not counted: the writer's final report goes to stdout, not to an agent
(`manager.py:93,100,102`).

## 2. Does the producer -> consumer model fit?

Partly. The producer side fits well. Every producer except R2 has a fixed Pydantic
output type, so hand-made snapshots are easy. A spec written by hand checks them
(see section 3). The consumer side does not fit `handshake infer`:
- The real consumer of each link is an LLM prompt. The Python code between agents
  sits in `FinancialResearchManager`. It reads fields by attribute access on Pydantic
  objects, never with `data["key"]`.
- Most manager methods take the producer data as the second or later parameter.
  `infer` always looks at the first parameter after `self`. In 6 of the functions I
  tried, that was the user's `query` string.
- Two links pass the whole object (`model_dump` / `model_dump_json`) and read no
  named field in code (L6, L8). The analyst links (L4, L5) go through a callback that
  the SDK calls.

## 3. What infer found

Setup for all runs: a local work directory, commands run from there. `F=../../src/openai_openai-agents-python/examples/financial_research_agent/manager.py`.
`H` is `handshake` 0.9.0 from PyPI. The snapshots are hand-made. Their shapes come from the
Pydantic classes. The financial query comes from
`examples/financial_research_agent/main.py:15-16`. The research_bot query comes from
`examples/research_bot/sample_outputs/vacation.txt:4`. The script that writes them is
a small local script. No run printed a line that starts
with `WARN`. Each run printed "reads no fields from its input" and indented notes,
wrote no spec and exited 2.

**L1 planner -> search**
- `$H infer --producer planner --consumer search --source $F:_search --name ...` gave exit 2:
  ```
  manager.py:_search reads no fields from its input.
    line 171: 'item' is used as a whole; the inferred contract may be incomplete
    line 171: 'item' is used as a whole; the inferred contract may be incomplete
    line 179: 'item' is used as a whole; the inferred contract may be incomplete
    line 180: 'item' is used as a whole; the inferred contract may be incomplete
  ```
- `--source $F:FinancialResearchManager._search` gave exit 2: `Error: Function 'FinancialResearchManager._search' not found in ...manager.py`.
- `--source $F:_perform_searches` gave exit 2: `line 143: 'search_plan' is used as a whole`.
- Read: `searches`, `searches[].query`, `searches[].reason` (3). Found: 0.
- Misses: attribute access on a Pydantic model (`item.query`, `search_plan.searches`),
  list items (slice and comprehension at :141-144), f-string prompt (:171). Also, `_search`
  gets one list item, not the producer's output.

**L2 search -> writer**
- `--producer search --consumer writer --source $F:_report_input` gave exit 2: `line 282: 'query' is used as a whole`.
  `infer` analyzed `query`, not `search_results`.
- Read: `summary` (`manager.py:181`, `search_summary.summary`). The variable is local, set from
  `result.final_output_as(...)` at :174, not a parameter. Found: 0.
- Misses: attribute access, data in a local variable rather than a parameter, wrong parameter
  analyzed, whole-object `model_dump` into a JSON prompt (:284).
- I also tried the citation helper in `examples/web_search_utils.py`:
  `--source ../../src/openai_openai-agents-python/examples/web_search_utils.py:extract_web_search_source_urls --out -`
  gave exit 2 (`line 62: 'items' is used as a whole`).
  `:get_field` gave exit 2 (`line 16: 'obj' calls .get() with a non-literal key`). These read SDK run
  items, not the agent's output type, so I did not count them as fields.

**L3 search -> verifier**
- `--producer search --consumer verifier --source $F:_verification_input` gave exit 2: `line 264: 'query' is used as a whole`.
- Read: `sources`, `sources[].url` (`manager.py:269`). Found: 0.
- Misses: wrong parameter analyzed (3rd parameter), nested list comprehension with attribute access.

**L4 financials -> writer, L5 risk -> writer**
- `--producer financials --consumer writer --source $F:_summary_extractor` gave exit 2: `line 65: 'run_result' is used as a whole`.
- The same run with `--producer risk` gave the same output.
- Read: `summary` once per link (`run_result.final_output.summary`, :65). Found: 0 per link.
- Misses: attribute access through the SDK `RunResult` wrapper (`.final_output.summary`).
  The function is a callback that the SDK calls (`as_tool(custom_output_extractor=...)`).

**L6 writer -> verifier**
- `--producer writer --consumer verifier --source $F:_verification_input` gave exit 2: `line 264: 'query' is used as a whole`.
- `--source $F:_verify_report` gave exit 2: `line 251: 'query' is used as a whole`.
- Read by name in code: none (0). The whole report goes to the verifier LLM as `report.model_dump(mode="json")` (:266).
- Misses: none in the count. The prompt use of `short_summary`, `markdown_report` and
  `follow_up_questions` cannot be seen by a code parser.

**L7 verifier -> writer (revision)**
- `--producer verifier --consumer writer --source $F:_revise_report` gave exit 2: `line 234: 'query' is used as a whole`.
- `--source $F:_produce_verified_report` gave exit 2 with 4 notes, all on `query` (lines 111, 112, 116, 117).
- Read: `verified` (:113, :118). Found: 0.
- Misses: attribute access on a local variable (the result of `_verify_report`), wrong parameter
  analyzed, whole-object `model_dump_json()` in an f-string (:121, :236).

**L8 writer -> writer (revision)**
- `--producer writer --consumer writer --source $F:_revise_report` gave exit 2: `line 234: 'query' is used as a whole`.
- Read by name: none (0). `report.model_dump_json()` in an f-string (:235).

**R1 research_bot planner -> search**
- `--producer rb_planner --consumer rb_search --source ../../src/openai_openai-agents-python/examples/research_bot/manager.py:_search`
  gave exit 2, with `line 95: 'item' is used as a whole` twice.
- `:_perform_searches` gave exit 2: `line 71: 'search_plan' is used as a whole`.
- Read: `searches`, `searches[].query`, `searches[].reason` (3). Found: 0.
- Misses: the same as L1.

**R2 research_bot search -> writer**
- `--producer rb_search --consumer rb_writer --source .../research_bot/manager.py:_write_report` gave exit 2: `line 107: 'query' is used as a whole`.
- Read by name: none (0). The output is free text. A snapshot must have an object as
  `output`, so I had to wrap the text under a made-up key `text`.

**handshake test**
- `$H test` (after all infer runs) gave exit 2:
  `No spec files in ./handshake/specs. Write one, or run 'handshake infer' or 'handshake init'.`
- I wrote two specs by hand (`planner-to-search-manual.yaml` for L1, `verifier-to-writer-manual.yaml` for L7)
  and ran `$H test` again. It printed `3 passed (total: 3)` and exited 0.
- Check that the spec can fail: I removed `reason` from `searches[0]` in the planner snapshot.
  `$H test` printed `FAIL planner-to-search-manual / apple_drivers`, `'reason' is a required property`,
  and exited 1. After I restored the file, it exited 0. The failure line does not name the path
  (`searches[0].reason`).

Fields found / total read: 0 / 12

## 4. Unsupported read forms

| form | example file:line | how often in the example |
|---|---|---|
| Attribute access on a Pydantic model (`item.query`, `verification.verified`) | `examples/financial_research_agent/manager.py:171` | 12 reads in the financial manager (:65, :130, :143, :171 x2, :179, :180, :181, :113, :118, :269 x2) and 4 in research_bot (:60, :71, :95 x2) |
| Producer data is not the first parameter, so `infer` analyzes `query` | `manager.py:275-279` (`_report_input(self, query, search_results)`) | 6 functions: `_report_input`, `_verification_input`, `_verify_report`, `_revise_report`, `_produce_verified_report`, research_bot `_write_report` |
| List items (slice, comprehension, `for` over a list of models) | `manager.py:141-144`, `manager.py:269` | 3 (financial :143, :269; research_bot :71) |
| Producer data in a local variable, not a parameter | `manager.py:174,181` (`search_summary`), `manager.py:112-113` (`verification`) | 2 |
| Whole object serialized into a prompt (`model_dump`, `model_dump_json`, `str()`) | `manager.py:266`, `manager.py:235-236` | 7 in the financial manager (:65, :121, :235, :236, :266, :267, :284) and 1 in research_bot (:101) |
| f-string or JSON prompt as the real consumer | `manager.py:171`, `manager.py:262-273`, `manager.py:280-287` | 5 in the financial manager (:171, :233-237, :262-273, :280-287, :93 to the user) and 2 in research_bot (:95, :107) |
| Callback that the framework calls (`custom_output_extractor`) | `manager.py:61-65,198,203` | 1 function, used by 2 links |
| Class-qualified method name not accepted in `--source` | `manager.py:170` (`FinancialResearchManager._search`) | Every consumer is a method of the manager. A bare method name works. |
| Helper with a non-literal key (`obj.get(key)`, `getattr(obj, key, None)`) | `examples/web_search_utils.py:14-18` | 1 helper, called 13 times in `web_search_utils.py` (:24-43, :62-70) |

## 5. Silent-breakage risk

Found. Three concrete cases. None of them uses a `.get("x", default)` read on the agent's
output type, because those models have no defaults. All three swallow a missing field
or a broken contract and let the run continue with less data.

1. Search link (L2/L3), default reads on producer data. `examples/web_search_utils.py:14-18`:
   ```python
   def get_field(obj: Any, key: str) -> Any:
       if isinstance(obj, Mapping):
           return obj.get(key)
       return getattr(obj, key, None)
   ```
   This reads `raw_item.action.sources[].url` (`web_search_utils.py:62-68`) and the
   `url_citation` annotations (:24-49). `action.sources` is only present because
   `examples/financial_research_agent/agents/search_agent.py:25` sets
   `response_include=["web_search_call.action.sources"]`. If that setting is removed, or the
   item shape changes, `get_field` returns `None`. Then `sources` is empty. If the answer also
   has no citations, `_search` returns `None` (`manager.py:176-177`) and the search counts
   as "failed" with no error message. `title` also falls back to the URL without any notice
   (`web_search_utils.py:50`).
2. Search link (L2), broken contract swallowed. `manager.py:185-186`
   (`except Exception: return None`) catches any error in `_search`. Two examples: an
   `AttributeError` if `FinancialSearchSummary.summary` is renamed (:181), and a type error
   from `final_output_as` (:174). `_perform_searches` never checks for an empty result
   (:168). If every search fails, the writer still runs with `"evidence": []` (:284). research_bot
   has the same pattern (`examples/research_bot/manager.py:102-103`).
3. Analyst links (L4/L5), broken contract turned into tool text. `_summary_extractor` reads
   `run_result.final_output.summary` (`manager.py:65`). It runs inside the function tool
   built by `as_tool` (`src/agents/agent.py:1073-1074`). That tool has
   `failure_error_function=default_tool_error_function` (`src/agents/agent.py:622,1112`), and
   the error is logged as "Error running tool (non-fatal)" (:1108). If `AnalysisSummary.summary`
   is renamed, the writer gets "An error occurred while running the tool. Please try again."
   (`src/agents/tool.py:1997-2002`) in place of the analysis, and the report is still written.

None of these reads uses `data["key"]` / `.get("key")` on a parameter, so `handshake infer`
could not have pointed at them.

## 6. Setup

7 steps:
1. Read the README "Limits" section and the CLI reference.
2. Create a work directory and `handshake.yaml` (`project_name: ...`).
3. Find the default `specs_dir` and snapshot path. The task gave only the snapshot path,
   so I ran `handshake init` in a temp dir to see the defaults, then deleted it.
4. Create 8 snapshot folders and write 9 snapshots by hand, through a small script. The
   shapes come from the Pydantic classes.
5. Run `handshake infer` 17 times: 13 on the financial manager, 2 on `web_search_utils.py`
   and 3 on research_bot. One of them failed on a class-qualified name.
6. Run `handshake test`. With no specs it exits 2.
7. Write 2 specs by hand, run `handshake test`, and check that a spec can fail.

What was awkward:
- There is no option to choose which parameter holds the producer data. `infer` always takes
  the first one after `self`, and the docs do not say this. Here that was `query` in 6 functions.
- For attribute access the note says `'item' is used as a whole`. That is wrong for `item.query`:
  the code reads a field, and the tool does not support that form. The note repeats for two reads
  on the same line (`line 171` twice, research_bot `line 95` twice).
- When `infer` finds no fields it writes no spec and exits 2. So `handshake test` has nothing to
  run, and every spec had to be written by hand.
- `--source manager.py:FinancialResearchManager._search` is rejected, but `manager.py:_search` works.
  If two classes in one file had a method with the same name, I could not pick one.
- A free-text producer (R2) must be wrapped in a made-up key, because snapshot `output` must be an object.
- The `test` failure message does not give the path of the missing field inside the array.

## Tool bugs

None. No crash or traceback. Every `infer` run exited with code 2 and a message. The limits
above (first parameter only, no attribute access, no class-qualified names) are design limits,
not crashes.

## Summary row

| openai-agents-python | Pydantic output types read by attribute in an orchestrator class, then put in f-string/JSON prompts; agent-as-tool with free-text result; 1 free-text link | partly | 0/12 | Attribute access on Pydantic models, and producer data is not the first parameter (infer analyzed `query`) | yes (searches and analyst tool errors are swallowed: `manager.py:185-186`, `web_search_utils.py:14-18` default reads, `as_tool` default error function) |

- Typed links (Pydantic/TypedDict/dataclass/Zod): 9 (L1-L8, R1). L4/L5 become free text at the tool boundary.
- Free-text links: 1 (R2). Every link ends as an LLM prompt.
- Shared-state links: 0.
- Links where data is passed into helper functions: 10 (all). Each one goes through a manager method (`_search`, `_report_input`, `_verification_input`, `_revise_report`) or the `_summary_extractor` callback.
