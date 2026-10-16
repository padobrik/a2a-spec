# OpenAI Agents SDK (JS): financial research agent

Run on 2026-10-17 with agent-handshake 0.9.0 from PyPI. The snapshots and specs were written by hand in a local work directory and are not committed; each one's source is given below.

- Repository: openai/openai-agents-js
- Commit: 9687b54
- Example: `examples/financial-research-agent/`
- Framework: OpenAI Agents SDK (`@openai/agents`)
- Language: TypeScript, with Zod output types

The example writes a financial report. `FinancialResearchManager` (manager.ts:44)
runs each agent with `run()` and passes the results along. The planner returns a
search plan (agents.ts:41-54). The search agent runs up to 15 searches in parallel
and returns free text (agents.ts:73-78, manager.ts:93-123). The writer turns the
search summaries into a report (agents.ts:114-129). It can call two analyst agents,
fundamentals and risk, as tools (manager.ts:29-42). The verifier checks the report
against the summaries (agents.ts:88-104). If the check fails, the writer revises
the report, up to 2 times (manager.ts:57-73). All files below are under
`examples/financial-research-agent/`. The example has 8 links, so research-bot was
not needed.

## 1. How the agents are linked

| # | Link | Producer | Consumer | Data form | file:line |
|---|------|----------|----------|-----------|-----------|
| 1 | planner -> search | FinancialPlannerAgent (`FinancialSearchPlan`) | `performSearches`, then `search(item)` for each list item | Zod object; list items go to a helper method, then into a prompt string | manager.ts:86-90, 95, 101-102, 116 |
| 2 | search -> writer | FinancialSearchAgent (no output type) | `writeReport` via `formatSearchResults` | Free text: `String(result.finalOutput)`, joined into the prompt | manager.ts:119, 16-19, 130 |
| 3 | search -> verifier | FinancialSearchAgent | `verifyReport` (2nd param) | Free text in the prompt | manager.ts:141 |
| 4 | writer -> verifier | FinancialWriterAgent (`FinancialReportData`) | `verifyReport` (1st param) | Zod object; one field read into a template literal | manager.ts:141 |
| 5 | verifier -> writer (revise) | VerificationAgent (`VerificationResult`) | `reviseReport` (3rd param), loop in `run` | Zod object; `issues` goes into the prompt, `verified` drives the loop | manager.ts:159, 59, 69, 71 |
| 6 | writer -> writer (revise) | FinancialWriterAgent | `reviseReport` (2nd param) | Zod object serialized whole with `JSON.stringify` into the prompt | manager.ts:162 |
| 7 | fundamentals -> writer | FundamentalsAnalystAgent (`AnalysisSummary`) | `summaryExtractor` | Tool call (`asTool`); custom extractor reads `RunResult.finalOutput.summary` | manager.ts:23-27, 31-35 |
| 8 | risk -> writer | RiskAnalystAgent (`AnalysisSummary`) | `summaryExtractor` (same function) | Tool call, same as 7 | manager.ts:23-27, 36-40 |

Not counted (the consumer is the manager or the console, not an agent): the writer's
`short_summary`, `markdown_report` and `follow_up_questions` are printed at
manager.ts:74-79.

Count: 8 links. 6 typed with Zod (1, 4, 5, 6, 7, 8; links 7 and 8 are also tool calls),
2 free text (2, 3). No shared state.

## 2. Does the producer -> consumer model fit?

Partly. Each agent returns one value from `run()`, and Zod gives it a fixed shape.
That fits the model. But the consumers are methods of one manager class. They take
several parameters, and the producer data is often not the first one
(`reviseReport(query, report, verification, searchResults)`, manager.ts:147-151).
Most data ends up inside prompt strings. The search agent returns plain text, which
a snapshot cannot hold. The analyst links go through the SDK's `RunResult` wrapper.
Only links 1 and 4 fit cleanly, and link 1 only at the top level.

## 3. What infer found

Setup: `handshake.yaml` with `project_name: openai-agents-js-financial`. Snapshots
were written by hand. Planner, writer and verifier values come from
`manager.test.ts:17-27, 59-64, 99-104`. The analyst `{"summary": ...}` shape comes
from agents.ts:9-13 (the text is a placeholder, since the repo has no sample). The
search snapshot is the string shape from manager.test.ts:108. `M` stands for
`../../src/openai_openai-agents-js/examples/financial-research-agent/manager.ts`.

**Link 1, planner -> search**
- `handshake infer --producer planner --consumer search --source M:performSearches --name planner_to_search`
- Wrote the spec. Found `searches` (required, line 95, type array). No WARN. Exit 0.
- Misses: `searches[].query` and `searches[].reason`. They are read in `search(item)`
  at line 116. The items reach it through `searchPlan.searches.slice(...)` and
  `this.search(item)` (lines 95, 101-102). The tool does not follow list items or
  helper calls. It printed no WARN here and did not set `reads_unknown_keys`.
- Second try: `--source M:search` (the helper, first param `item`). It found
  `query` and `reason` (line 116) but printed `FAIL: 'query' is read by search (line 116)
  but planner never sent it in any snapshot`, the same for `reason`, and exit 1.
  The fields are inside list items, not at the top of the planner output.
- Probe: I removed `query` from a planner item in a copy (`probe_items/`).
  `handshake test` still gave `4 passed`, exit 0.

**Link 2, search -> writer** and **Link 3, search -> verifier**
- `handshake infer --producer search --consumer writer --source M:writeReport --name search_to_writer`
- Also tried `--source M:formatSearchResults`.
- Both gave `Error: Snapshot handshake/snapshots/search/query0_001.json has a 'output'
  field that is not an object.` and exit 2. A free-text producer cannot be recorded.
  0 fields are read by name, so nothing was missed.

**Link 4, writer -> verifier**
- `handshake infer --producer writer --consumer verifier --source M:verifyReport --name writer_to_verifier`
- Wrote the spec. Found `markdown_report` (required, line 141, type string). This is a
  read inside a template literal. No WARN. Exit 0. No misses.

**Link 5, verifier -> writer (revise)**
- `handshake infer --producer verifier --consumer writer --source M:reviseReport --name verifier_to_reviser`
- Output: `reviseReport reads no fields from its input.` and
  `line 154: 'query' is used as a whole; the inferred contract may be incomplete`.
  Exit 2.
- The tool reads only the first parameter, which is `query`. `verification` is the
  third parameter.
- Misses: `issues` (line 159). `verified` is read in `run` at lines 59 and 69 on a
  local variable, not a parameter.
- Also tried `--source M:run --producer verifier --consumer manager`. It printed the
  same "reads no fields" message with three `'query' is used as a whole` lines
  (47, 56, 61). Exit 2.

**Link 6, writer -> writer (revise)**
- Same command with `--producer writer --consumer writer`. Same result, exit 2.
- The report is the second parameter and is serialized whole with `JSON.stringify`
  (line 162). No field is read by name. I count 0 named reads here. All 3 fields go
  into the prompt.

**Links 7 and 8, fundamentals/risk -> writer**
- `handshake infer --producer fundamentals --consumer writer --source M:summaryExtractor --name fundamentals_to_writer`
- The same with `--producer risk`.
- Both gave `FAIL: 'finalOutput' is read by writer (line 26) but fundamentals never
  sent it in any snapshot` (and the same for risk). Exit 1.
- The consumer takes the SDK's `RunResult`, not the agent output. The parser saw the
  path `finalOutput.summary` correctly, but the snapshot holds the output itself.
- Check: a snapshot wrapped as `{"finalOutput": {"summary": ...}}`
  (`fundamentals_wrapped`, `--out -`) gave a correct spec, with `finalOutput.summary`
  required at line 26. So the read form works; only the wrapper does not match.
- Missed: `summary`, once per link.

**handshake test** (after moving the free-text snapshot out to `excluded_free_text/`):
`4 passed (total: 4)`, exit 0. If I delete `markdown_report` from a writer snapshot,
it gives `FAIL writer_to_verifier / initial ... 'markdown_report' is a required property`,
exit 1. `handshake infer --check`: both specs `OK`, exit 0.

Fields found / total read: 2 / 8. This counts fields read by name in links 1, 4, 5, 7
and 8: searches, query, reason, markdown_report, verified, issues, summary x2. It
would be 4 / 8 if I also counted the two `finalOutput.summary` reads that the parser
saw but could not match to the snapshots. Not counted: the whole-object read at
line 162 and the free-text links.

## 4. Unsupported read forms

| Form | Example | How often in the example |
|------|---------|--------------------------|
| Producer data in a parameter other than the first | `reviseReport(query, report, verification, ...)`, manager.ts:147-151, reads at 159 and 162; `verifyReport(report, searchResults)`, searchResults at 141 | 1 function, 3 parameters (links 3, 5, 6) |
| List items passed to a helper method | `searchPlan.searches.slice(0, MAX_SEARCHES)` then `this.search(item)`, manager.ts:95, 101-102, 116 | 1 (link 1, 2 fields). No WARN was printed. |
| Framework result wrapper (`RunResult.finalOutput.x`) | `String(runResult.finalOutput.summary)`, manager.ts:26 | 1 function, used by 2 links. Also `result.finalOutput!.searches` at manager.ts:88. |
| Local variable from a call, not a parameter | `verification.verified`, `verification.issues`, `report.short_summary` in `run`, manager.ts:59, 69, 71, 74-79 | 1 function, 6 reads |
| Whole object serialized into a prompt | `JSON.stringify(report, null, 2)`, manager.ts:162 | 1 |
| Free-text producer (the output is a string, not an object) | `return String(result.finalOutput)`, manager.ts:119 | 2 links. A string snapshot also stops every `handshake test` run with exit 2, even when no spec uses that producer. |

These forms worked: a field read inside a template literal (manager.ts:141), and a
nested read under the wrapper (manager.ts:26), once the snapshot was reshaped.

## 5. Silent-breakage risk

Yes, but latent. `summaryExtractor` (manager.ts:23-27) types its input as
`RunResult<unknown, Agent<unknown, any>>`, so `finalOutput` is `any`. It returns
`String(runResult.finalOutput.summary)`. The fundamentals and risk agents share
this extractor (manager.ts:34, 39), and today both use `AnalysisSummary`
(agents.ts:18, 64), which has `summary`. If one agent's `outputType` changes or
renames `summary`, the compiler says nothing because of `any`. `String(undefined)`
then sends the text `"undefined"` to the writer as the tool result, with no error.

A smaller case: `search` returns `String(result.finalOutput)` (manager.ts:119).
`finalOutput` is typed `T | undefined` (packages/agents-core/src/result.ts:267-285).
If it is undefined, the text `"undefined"` gets past the blank filter
(manager.ts:48-50) and goes into the writer's prompt. The search agent has no tools
that need approval, so this is unlikely today.

No `?.`, `??` or `||` fallbacks are used on agent output in the example. The
`result.finalOutput!` assertions (manager.ts:88, 90, 133, 144, 168) are checked
only at compile time.

## 6. Setup

9 steps:
1. Write `handshake.yaml`.
2. Create the snapshot folders.
3. Write 9 snapshot files by hand from `manager.test.ts` and the Zod schemas.
4. Find out which parameter infer reads.
5. Run infer 10 times.
6. Move the free-text snapshot out so that `handshake test` can run.
7. Run `handshake test`.
8. Run `handshake infer --check`.
9. Run two probe copies.

What was awkward:
- Infer reads only the first parameter. README and cli-reference do not say so. I
  found it in the installed source (`infer/ts_consumer.py` `_first_parameter`).
  There is no option to pick another parameter, so the manager methods with 3-4
  parameters cannot be checked.
- A free-text snapshot is rejected, and it stops the whole `test` run (exit 2). It
  had to be moved out of `handshake/snapshots/`.
- Missing list-item fields give no WARN and no `reads_unknown_keys`, so the
  planner spec looks complete when it is not.
- `inferred_from` stores the path as I typed it (`../../src/...`). The spec breaks if
  the work directory moves.
- In zsh, `$M:search` is read as a history modifier ("bad substitution"). This is a
  shell problem, not a tool problem; I quoted it as `"${M}:search"`.

## Tool bugs

None. No crash and no traceback. Notes that are not blocking bugs:
- The list-item miss in link 1 gave no WARN, even though the docs promise a WARN when
  input is given to another function.
- The "first parameter only" rule is not in the docs.

## Summary row

| openai-agents-js (financial-research-agent) | Zod objects via manager methods, free text, agent-as-tool with RunResult extractor | partly | 2/8 | producer data in non-first parameter; list items passed to helper; RunResult wrapper | yes (latent: `String(runResult.finalOutput.summary)` on `any`, manager.ts:26) |

Counts:
- typed links (Zod): 6 (links 1, 4, 5, 6, 7, 8)
- free-text links: 2 (links 2, 3)
- shared-state links: 0
- links where data is passed into helper functions: 3 (link 1: items to `search(item)`, manager.ts:102; links 2 and 3: summaries to `formatSearchResults`, manager.ts:130, 141)
