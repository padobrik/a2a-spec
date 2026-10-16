# Recon summary

Five open-source multi-agent projects, run with agent-handshake 0.9.0 from PyPI.
Snapshots were written by hand from each project's code, tests and sample
outputs. No project code was run and no model was called. The details, with
file and line references, are in one file per project.

The fields, snapshots and specs are frozen in `benchmarks/recon/`;
`make benchmark` recomputes the found / total column.

## Results

| Project | Type of links | Model fits | Fields found / total | Main reason for misses | Risks: explicit / disputed |
|---|---|---|---|---|---|
| [GPT Researcher](gpt-researcher.md) (LangGraph, Python) | Shared graph state (TypedDict, read as a dict with `.get`), subgraph input and result dicts, free text and model JSON in state | partly | 38 / 77 (65 / 77 with each helper run by hand) | The node passes the whole state to a helper method (37 of 39 misses) | 2 / 1: the fact checker reads `introduction` and `conclusion` with a `""` default from unchecked model JSON the writer spreads into state; the publisher hides bad `headers` with `or {}` |
| [OpenAI Agents SDK, Python](openai-agents-python.md) (financial research) | Pydantic outputs read by attribute in an orchestrator class, then put in prompts; agents as tools | partly | 0 / 12 | Attribute access on Pydantic models; the producer data is not the first parameter | 0 / 4: swallowed search and analyst tool errors, a helper that reads framework items with defaults (framework internals, latent) |
| [OpenAI Agents SDK, TypeScript](openai-agents-js.md) (financial research) | Zod outputs passed through manager methods, free text, agents as tools | partly | 2 / 8 | The producer data is not the first parameter; list items go to a helper; the SDK result wrapper | 0 / 2: `String(runResult.finalOutput.summary)` on an `any` value sends `"undefined"` if the field is renamed (latent) |
| [Microsoft Agent Framework](agent-framework.md) (switch-case workflow) | Dataclass messages, Pydantic output as JSON text, chat text, shared workflow state | partly | 0 / 19 | Attribute access on dataclass and Pydantic messages; shared state on the second parameter | 0 / 1: `getattr(email, "email_content", "")` on shared state (latent: the state is always set today) |
| [CrewAI flow template](crewai-flow-template.md) (`crewai create flow`) | Dict parameter, shared Pydantic flow state, prompt placeholders, free-text task context | partly | 1 / 11 | Flow steps take no parameter and read `self.state`; agents exchange text inside the framework | 0 / 4: `payload.get("topic", "AI Agents")` on an external trigger payload, empty prompt values, state and output defaults |
| **Total** | | partly in 5 of 5 | **41 / 127 (32%)** | | **2 / 12** |

The model fits each project partly. Every project has clear producers and
consumers, and every producer output has a fixed shape. The gap is on the
consumer side: in four of five projects the consumer does not read a dict
parameter with `["key"]`, `.get()` or `in`.

Risks are split as follows (one line each in `benchmarks/recon/<project>/risks.md`):

- **Explicit**: a consumer agent reads a producer agent's output with a
  default, and the producer does not guarantee the field. 2 risks, both in
  GPT Researcher.
- **Disputed**: the default reads an external payload or user input, sits in
  framework internals, or only breaks after a future change (latent). 12
  risks, in all five projects.

Every project reads some output with a default, but only one project has a
default that hides a break between two agents today.

## Links

57 links in total (20, 10, 8, 10, 9). A link can be in more than one group.

| Group | Links | Share | Notes |
|---|---|---|---|
| Typed (Pydantic, TypedDict, dataclass, Zod) | 43 | 75% | 62% (23 of 37) without GPT Researcher, whose TypedDict state is read as a plain dict |
| Free text | 22 | 39% | Almost all of it goes into a prompt. Code parses text in two projects only, and only as JSON (Agent Framework `model_validate_json`, GPT Researcher `json_repair`). No `re.search`, `split` or substring check on agent text was found |
| Shared state | 25 | 44% | 20 of them in GPT Researcher; also CrewAI `self.state` (2) and Agent Framework `ctx.get_state` (3). The main form of link in 1 project of 5 |
| Data passed into a helper function | 36 | 63% | In every project. The whole state or object goes to a method in the same file (GPT Researcher, OpenAI Agents SDK) or list items go to a helper (OpenAI Agents SDK in both languages) |

## Why fields were missed

86 of 127 field reads were missed. By reason (approximate, a read can have
two reasons):

| Reason | Misses | Projects |
|---|---|---|
| The object is passed to a helper in the same file, or list items are read in a helper | about 40 | GPT Researcher (37), OpenAI Agents SDK TS (2), CrewAI (framework helpers) |
| Attribute access on a typed object (`item.query`, `detection.email_id`, `self.state.topic`, `result.raw`) | about 33 | Agent Framework (16), OpenAI Agents SDK Python (12), CrewAI (3), TS (2, through the result wrapper) |
| The producer data is not the first parameter, or sits in `self` / `ctx` / a local variable | about 10 | OpenAI Agents SDK Python (6 functions analyzed the `query` string), TS, Agent Framework, CrewAI |
| Free text or prompt placeholders | about 4 | CrewAI |

## Recommended order for phase 4

1. **4.A Contract from types.** The threshold (20% typed links) is met: 75%
   overall, 62% without GPT Researcher. Attribute access on a typed parameter
   is the top miss in three projects. The type annotation also tells which
   parameter holds the producer data, which fixes the "first parameter only"
   misses in both OpenAI Agents SDK projects.
2. **4.F Analysis across functions in one file, with list items.** It is the
   main cause in GPT Researcher (37 of 39 misses) and appears in three other
   projects. In the projects' own code, every helper was in the same file as
   its caller. This moves
   4.F up from its default last place.
3. **4.C Snapshots from several runs.** The plan says to do it in any case.
   The recon gives no evidence for or against, because every snapshot was
   written by hand. Note: an agent whose output is plain text cannot be
   recorded today (`output` must be an object), and one such snapshot stops
   every `handshake test` run.
4. **4.E Shared state.** The main form of link in one project (GPT
   Researcher, 20 of 20 links), and present in two more. Write the one-page
   design note first, as the plan says. The hard part seen in the recon is
   that one consumer reads fields written by two to five producers, so one
   spec per producer does not fit.
5. **4.D Text contracts.** The condition (text parsed by code in at least two
   projects) is met only for JSON inside text, in two projects. No project
   checks text with regular expressions, splits or substrings. Do only
   `embedded_json`, or skip 4.D.

## Gaps in agent-handshake found during the runs

None of these blocked a run, so no tool code was changed in this phase.

1. `infer --allow-missing x` writes a spec that `infer --check` rejects at
   once when the consumer reads `data["x"]` ("reads 'x' with [] but the spec
   makes it optional"). The "Regenerate" command that `--check` prints drops
   `--allow-missing`, so it fails too. Found in the CrewAI run. This came in
   with 0.9.0.
2. `x = data.get("k") or {}` followed by `x.get("sub")` records `k` but not
   `k.sub`, with no WARN and no `reads_unknown_keys`. The spec looks complete.
   8 reads in GPT Researcher.
3. Reads of list items (`for r in data.get("results")`, or items passed to a
   helper) are not followed and give no WARN. The README says list items are
   not followed, but the run shows no sign of it. GPT Researcher, OpenAI
   Agents SDK TS.
4. An attribute read such as `detection.spam_decision` is reported as
   "'detection' is used as a whole", which is not what the code does.
5. `infer` analyzes only the first parameter (after `self`). The README and
   the CLI reference do not say so. A method name with its class
   (`Manager._search`) is not accepted in `--source`.
