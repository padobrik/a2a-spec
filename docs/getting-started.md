# Getting Started with a2a-spec

## Installation

```bash
pip install a2a-spec
```

For semantic features (embedding-based comparisons):

```bash
pip install a2a-spec[semantic]
```

For development:

```bash
pip install a2a-spec[dev]
```

## Quick Start

### 1. Initialize a project

```bash
a2aspec init --name my-project
```

This creates the standard directory structure with example specs and scenarios.

### 2. Define your specs

Edit `a2a_spec/specs/` to define what each agent expects from others. A spec is a YAML file describing:

- **Structural** requirements (JSON Schema)
- **Semantic** rules (embedding similarity, entailment)
- **Policy** rules (PII detection, forbidden patterns)

### 3. Create adapters

Wrap your agents with adapters so a2a-spec can call them:

```python
from a2a_spec import FunctionAdapter

async def my_agent(input_data: dict) -> dict:
    return {"category": "billing", "summary": "..."}

adapter = FunctionAdapter(fn=my_agent, agent_id="my-agent", version="1.0")
```

### 4. Record baselines

```bash
a2aspec record
```

### 5. Test in CI

```bash
a2aspec test --replay
```

This validates against saved snapshots with zero LLM calls.

## Next Steps

- [Core Concepts](concepts.md) — Understand specs, snapshots, replay, and diff
- [Writing Specs](writing-specs.md) — Detailed guide to spec YAML files
- [Writing Adapters](writing-adapters.md) — How to wrap your agents
- [CI Integration](ci-integration.md) — GitHub Actions, Jenkins, etc.
