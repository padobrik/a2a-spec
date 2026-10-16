# Core Concepts

## Spec

A **spec** is a YAML file that defines the contract between two agents — what the consumer expects from the producer. Specs have two layers:

- **Structural** — JSON Schema defining required fields, types, and constraints
- **Policy** — Hard rules that must never be violated (e.g., "no PII in output")

## Snapshot

A **snapshot** is a recorded LLM output for a specific input, stored as JSON and committed to git. Snapshots serve as baselines for deterministic replay.

## Replay

**Replay** means running validation against saved snapshots instead of calling live agents. This enables fast, free, deterministic testing in CI — zero LLM calls required.

## Diff

A **diff** compares two agent outputs (typically old baseline vs. new recording) and reports:

- Structural changes (fields added, removed, type changed)
- Severity assessment (low/medium/high/critical)

## Adapter

An **adapter** wraps your agent so agent-handshake can call it. Adapters exist for plain async functions, HTTP endpoints, and A2A agents. Agents built with a framework are called from an async function.
