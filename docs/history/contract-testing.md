# Contract testing between agents (closed)

From February to October 2026 (0.1.0 to 0.10.0) agent-handshake tested the
data that one agent hands to the next. The direction was closed on 2026-10-17.
Its code, benchmarks and notes are in tag
[contract-testing-final](https://github.com/padobrik/agent-handshake/tree/contract-testing-final), the last commit
before the removal. The code there is the same as in the last release, 0.10.0;
the holdout suite was added after that release.

## What it did

1. `handshake record` called a producer agent through an adapter (a Python
   function, HTTP, or A2A 1.0) and saved its output as a snapshot in git.
2. A spec in YAML described the fields the consumer needs: a JSON Schema plus
   `regex` policy rules.
3. `handshake test` checked every snapshot against the specs, without model
   calls, from the CLI, the pytest plugin or the GitHub Action.
4. `handshake diff` compared snapshots with their committed versions and rated
   the drift by what the consumer reads.
5. `handshake infer` wrote the spec itself: it analyzed the consumer's source
   (Python with `ast`, TypeScript with tree-sitter) and listed the fields the
   code reads. `infer --check` failed CI when the spec and the code disagreed.

Steps 1 to 4 worked, but they needed a hand-written spec, which few users
would maintain. Step 5 was the bet: a contract taken from the code, with no
configuration.

## How it was measured

- **Recon.** Five open-source multi-agent projects (GPT Researcher, the OpenAI
  Agents SDK financial research example in Python and in TypeScript, Microsoft
  Agent Framework, the CrewAI flow template). For each one, the fields every
  consumer reads were listed by hand from the code, with snapshots written
  from the projects' tests and sample outputs. The first run (0.9.0) found
  41 of 127 fields (32%).
- **Two rounds of work driven by the recon misses.** Contracts from types
  (Pydantic, TypedDict, dataclasses, Zod; attribute reads) and analysis across
  helper functions in one file, list items and fallbacks (`or`, `??`). The
  result on recon (0.10.0): **107 of 127 fields (84%)**.
- **Holdout.** Five projects the analyzer had never seen (AI-Scientist-v2,
  Google ADK, LlamaIndex workflows, Mastra, Pydantic AI). The reference lists
  were committed before the first run, and no analyzer code was changed for
  them. The result: **20 of 126 fields (16%)**, with 7 fields reported that
  the consumer does not read.

## Why it was closed

The holdout misses were not about read forms the analyzer could learn:

- **49% of the missed fields never reach a function parameter.** The data
  travels through session state (Google ADK), files on disk (AI-Scientist) or
  events collected from a context (LlamaIndex). Static analysis of one
  function does not see it.
- **41% sit in framework step factories** (`createStep({ execute })` in
  Mastra) that cannot be named as a function, with the data inside a
  framework wrapper.
- **10%** were read forms not supported yet (spread copies, negative indexes).

Recon had overstated coverage: the analyzer was shaped on projects that pass
data as parameters, and new code mostly does not. Each framework would need
its own support, and the result would still miss state and files.

A short follow-up spike recorded field reads at run time instead (a tracking
proxy around the producer's output). It found more fields, but needed more
than 20 lines of integration per project, attributed some reads wrongly (reads
by callees, nested graphs) and depended on which branches the run took. It was
not continued.

## What carries over

- No model calls and no hidden passes: a check that cannot run says so and
  fails.
- Measure each rule on a benchmark before turning it on, keep the
  expectations fixed before the first run, and keep a holdout the rules were
  not tuned on.
- The CLI skeleton, exit codes, config loading and the report helpers stay in
  1.0.

## Where to find it

Everything below is in tag `contract-testing-final`.

- Code and tests: [`src/`](https://github.com/padobrik/agent-handshake/tree/contract-testing-final/src) and
  [`tests/`](https://github.com/padobrik/agent-handshake/tree/contract-testing-final/tests).
- Recon notes, per project: [`docs/recon/`](https://github.com/padobrik/agent-handshake/tree/contract-testing-final/docs/recon)
  ([summary](https://github.com/padobrik/agent-handshake/blob/contract-testing-final/docs/recon/summary.md),
  [holdout](https://github.com/padobrik/agent-handshake/blob/contract-testing-final/docs/recon/holdout.md)).
- Benchmarks and the scorer: [`benchmarks/`](https://github.com/padobrik/agent-handshake/tree/contract-testing-final/benchmarks)
  (`recon/`, `holdout/`) and `scripts/benchmark.py` (`make benchmark`).
- Design note on silent fallbacks (not implemented):
  [`docs/design/silent-fallbacks.md`](https://github.com/padobrik/agent-handshake/blob/contract-testing-final/docs/design/silent-fallbacks.md).
