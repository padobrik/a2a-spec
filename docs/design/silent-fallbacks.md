# Silent fallbacks: design note

Status: proposal for the owner's decision after phase 4.F. No code.

## The idea

A consumer agent reads another agent's output with a default:
`state.get("introduction", "")`, `getattr(email, "email_content", "")`,
`headers or {}`, `ticket.priority ?? "low"`. When the producer stops sending
the field, nothing fails: the consumer goes on with the default, and the result
is worse, not broken. Type checkers do not see it, because the default makes the
read valid.

The mode would find, without configuration, every place where an agent's output
is read with a default, and say for each whether the producer guarantees the
field: by its type (a required field of a model, TypedDict or Zod schema) or by
its recorded outputs (present in every snapshot).

## What the benchmark shows

Measured on the five recon projects (`benchmarks/recon/`) with the 4.F
analyzer. It finds 107 of the 127 fields the consumers read, which covers the
places where a default would sit.

| | GPT Researcher | CrewAI template | OpenAI SDK (Py) | OpenAI SDK (TS) | Agent Framework | Total |
|---|---|---|---|---|---|---|
| Reads of agent output with an explicit default (`.get(k, d)`, `or`, `getattr(o, k, d)`, `??`, `\|\|`) | 15 | 1 | 0 | 0 | 0 | 16 |
| Reads that return `None` when the key is missing (`.get(k)`, `?.`) | 61 | 0 | 0 | 0 | 0 | 61 |
| Explicit risks found by hand (agent reads agent output, producer does not guarantee) | 2 | 0 | 0 | 0 | 0 | 2 |
| Disputed risks found by hand (external input, framework internals, latent) | 1 | 4 | 4 | 2 | 1 | 12 |

How the 16 explicit defaults split:

- **3 reads behind the 2 explicit risks.** The fact checker reads
  `introduction` and `conclusion` with `""`, and the publisher reads `headers`
  with `or {}` (its six `headers.*` reads follow). In both cases the writer puts
  unchecked model JSON into the state.
- **9 reads of noise.** Five are loop counters the graph keeps for itself
  (`draft_revision_count` with 0). Four are list defaults (`research_data`,
  `diagrams`) that the producer always sets in code.
- **3 reads of user input, which is disputed:** the task's `source` and
  `task or {}`, and the CrewAI trigger payload's `topic`.
- **1 read that is unclear:** `sources or []`, which also comes from model
  JSON.

So a plain list of defaults would show 16 places (77 with `.get(k)`) to find 2
risks, about 1 useful line in 5.

## Why type and snapshots do not separate risk from noise

- **Snapshots.** All 3 risky reads are present in every recorded snapshot.
  The model returned the keys when the snapshots were recorded. The risk is that
  it may not next time. Meanwhile, 7 of the 9 noise reads look missing in some
  snapshots. They come from shared graph state, where one snapshot shows one
  node's output, not the merged state.
- **Types.** GPT Researcher declares `introduction` and `headers` in its
  `ResearchState` TypedDict, so by type they are guaranteed. TypedDict is not
  checked at run time, so the declaration is not true.
- **What does separate them** is where the producer's value comes from. In
  both explicit risks it is parsed model output that no schema validated
  (`json_repair` in the model call the writer uses). That is a producer-side analysis, not a
  consumer-side one.
- **Typed projects.** In the OpenAI Agents SDK and Agent Framework examples,
  outputs are Pydantic or Zod models validated by the framework. Consumers there
  read their parameters without defaults: the mode finds 0 places. Their 7
  risks are swallowed exceptions, framework defaults, an `any`-typed extractor
  and one default on shared workflow state (`ctx.get_state`), which the
  analyzer does not read. A default-read detector sees none of them.

## What it would take on the current analyzer

1. **Mark reads that have a default (small, about 2 to 3 days).** Both readers
   already record every read with its line and whether a missing key raises.
   Adding the kind of default (explicit value, `None`, `or`, `??`) and listing
   these reads per consumer, with the guarantee by type and by snapshots, uses
   what exists. This works when the user names the consumer function, as
   `infer` does today.
2. **No configuration (medium, 1 to 2 weeks).** Find the agent boundaries
   without `--source`, one framework at a time: LangGraph nodes and their state,
   CrewAI flow steps and `self.state`, OpenAI Agents SDK run results, Agent
   Framework executors. Shared state needs the producer map from 4.E (who
   writes each key) for the guarantee column to mean anything there.
3. **Tell risk from noise (large, 2 to 4 weeks or more).** Follow each field
   on the producer side and mark values built from unvalidated model output. In
   the benchmark, this alone keeps the 3 risky reads and drops the 9 noise reads.
   Without it, the mode shows about 5 lines per real risk.

## Questions the interviews can answer

- How often does a break between agents show up as worse output rather than an
  error? The benchmark has 2 such cases in 5 projects, both in the one project
  that passes plain dicts between agents.
- Do teams that use typed outputs (Pydantic, Zod) still lose data this way, or
  do their breaks come from swallowed errors instead? If the latter, a
  fallback detector does not help them.
- Would a list where 1 line in 5 is a real risk be read, or turned off?

## Summary for the decision

- The pattern is real. Every project reads some output with a default, but the
  data has only 2 explicit risks, both in one project.
- A consumer-side detector is cheap to start (step 1), but it is noisy.
- Separating risk from noise needs producer-side analysis of unvalidated model
  output (step 3). That is new work, not a narrowing of the current tool.
