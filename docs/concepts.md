# Core Concepts

## Spec

A **spec** is a YAML file that defines the contract between two agents — what the consumer expects from the producer. Specs have three layers:

- **Structural** — JSON Schema defining required fields, types, and constraints
- **Semantic** — Rules about the meaning of outputs (e.g., "summary must reflect input")
- **Policy** — Hard rules that must never be violated (e.g., "no PII in output")

## Snapshot

A **snapshot** is a recorded LLM output for a specific input, stored as JSON and committed to git. Snapshots serve as baselines for deterministic replay.

## Replay

**Replay** means running validation against saved snapshots instead of calling live agents. This enables fast, free, deterministic testing in CI — zero LLM calls required.

## Diff

A **diff** compares two agent outputs (typically old baseline vs. new recording) and reports:

- Structural changes (fields added, removed, type changed)
- Semantic drift (meaning has shifted beyond threshold)
- Severity assessment (low/medium/high/critical)

## Pipeline

A **pipeline** is a DAG of agents where data flows from one to the next. a2a-spec can test entire pipelines, validating each agent's output against its spec and checking end-to-end invariants.

## Adapter

An **adapter** wraps your agent so a2a-spec can call it. Adapters exist for plain async functions, HTTP endpoints, and LangChain runnables.
