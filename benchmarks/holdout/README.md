# Holdout benchmark

Five open-source projects that the analyzer was never developed or tuned on.
The format and counting rules are the same as in `benchmarks/recon/`
(see its README); `make benchmark` prints a separate total for each suite.

| Project | Framework | Language | Example |
|---|---|---|---|
| ai-scientist-v2 | none (plain Python stages) | Python | `launch_scientist_bfts.py` pipeline: ideation, experiments, write-up, review |
| google-adk | Google Agent Development Kit | Python | `core/python/deep-search` |
| llama-index-workflows | LlamaIndex Workflows | Python | `AgentWorkflow` in `llama-index-core` |
| mastra | Mastra | TypeScript | `template-github-review-agent` PR review workflow |
| pydantic-ai | Pydantic AI | Python | `examples/pydantic_ai_examples/flight_booking.py` |

## How it was built

The reference lists were written blind. They were built only from each project's
code, by people who did not run agent-handshake or the benchmark and did not read
the analyzer's source. They were committed (up to commit `3740145`) before the
analysis ran on them for the first time. No analyzer code was changed for these
projects. Each project's `NOTES.md` describes the example and its links, and
`SOURCES.md` lists where each snapshot comes from.

## First result

Analyzer of release 0.10.0, first run after the references were committed:

| Suite | Found | Total | False |
|---|---|---|---|
| recon | 107 | 127 (84%) | 0 |
| holdout | 20 | 126 (16%) | 7 |

The reasons are in `docs/recon/holdout.md`. Release 0.10.1 removes the 7 false
fields (a producer whose output is text or a list, and a substring test on
text) without changing the found fields: holdout is 20 of 126, 0 false.
