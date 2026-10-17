# Holdout result

The analyzer of 0.10.0 finds 84% of the fields on the projects it was developed
on (`benchmarks/recon/`) and 16% on five projects it never saw
(`benchmarks/holdout/`). The holdout reference lists were committed before the
first run, and no analyzer code was changed for them.

| Project | Found | Total | False | Main reason for misses |
|---|---|---|---|---|
| ai-scientist-v2 | 0 | 18 | 1 | Stages pass data through files on disk and model JSON parsed inside the consumer |
| google-adk | 0 | 24 | 3 | Agents share data through session state and model events |
| llama-index-workflows | 17 | 38 | 0 | Events collected from the context; a list copy and a negative index |
| mastra | 0 | 43 | 0 | The step function cannot be named with `--source` |
| pydantic-ai | 3 | 3 | 3 | Only one consumer reads fields; it is found |
| **Total** | **20** | **126 (16%)** | **7** | |

## Why fields were missed (106)

1. **Data that never reaches a parameter: 52 fields (49%).** The consumer gets
   the producer's output in some way other than a function parameter:
   - Google ADK keeps it in session state (`callback_context.state[...]`) and in
     the model events of the session (24 fields);
   - AI-Scientist writes it to files (`idea.json`, `*_summary.json`) and the
     next stage loads it inside its own function, or keeps it on `self`
     (18 fields);
   - LlamaIndex collects events from the context (`ctx.collect_events`) and
     reads `ctx.store` (10 fields).

   This is the gap the recon already showed for the CrewAI template and Agent
   Framework (shared state, 4.E) and for local variables (`final_output_as`).
   Both are in the backlog.
2. **A step function that cannot be named: 43 fields (41%).** Mastra steps are
   `const categorizeFiles = createStep({ ..., execute: async ({ inputData }) => ... })`.
   `--source file.ts:categorizeFiles` names a call, not a function. `execute`
   occurs once per step, so it is ambiguous. The producer's data is also one
   property (`inputData`) of a destructured parameter. The reads themselves are
   plain property reads and helper calls, which the analyzer supports.
3. **Read forms not supported: 11 fields (10%), all in LlamaIndex.** A list is
   copied with a spread (`llm_input = [*ev.input]`), its last item is read with
   a negative index (`llm_input[-1].blocks`), and a value is given to code in
   another module.

## Why false fields appeared (7)

- **6 fields.** The producer's output is not an object: it is text in Google
  ADK and a list in Pydantic AI. `infer` then has no keys, so it cannot reject a
  parameter that holds something else. It reads the framework context instead:
  `ctx.deps.web_page_text` and `ctx.usage` in Pydantic AI, and
  `callback_context.state.*` in ADK. With object outputs, the same situation is
  refused ("No parameter ... holds the producer's output").
- **1 field.** A substring test on a text parameter (`"I am done" in text`)
  counts as a key check.

Analyzing the AI-Scientist code also prints Python `SyntaxWarning`s, from
invalid escape sequences in that project's strings. The analyzer passes them
through to stderr.

## What the numbers say

- **Data paths, not read forms.** On recon, data mostly reaches the consumer
  as a parameter (a dict, a typed model, a list), and the analyzer reads it
  well. On holdout, it mostly does not: 52 of 126 fields arrive through state,
  events or files. Where the data is a parameter of a function `--source` can
  name, the analyzer finds 20 of 31 fields (65%). Counting the Mastra steps,
  which are parameters but cannot be named, it finds 20 of 74 (27%).
- **Recon overstates coverage on new code.** The analyzer was shaped on recon,
  and recon's projects pass data as parameters more often.
- **Caveats on the sample.** The LlamaIndex example is framework code, not an
  application. The Pydantic AI example has only 3 fields. Google ADK and
  AI-Scientist pass data through state and files by design.

## Options for the owner (not implemented)

- Name a step function by the variable it is assigned to, and treat a
  framework's input wrapper (`inputData`) like `RunResult.final_output`. This
  covers Mastra-style step factories: 43 fields here.
- When the producer's output is not an object, refuse a parameter whose reads
  are not in the output, as for objects. This removes the 6 false fields.
- A list built by spread, and negative indexes: 11 fields.
- Shared state, events and local variables (52 fields): 4.E and the backlog
  item, which the owner has put off.
