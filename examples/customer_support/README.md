# Customer Support Pipeline Example

This example demonstrates a complete a2a-spec workflow with a two-agent customer support pipeline:

1. **Triage Agent** — Classifies incoming support tickets by category and priority
2. **Resolution Agent** — Takes the triage output and generates a resolution

## Structure

```
customer_support/
├── agents/
│   ├── triage.py          # Triage agent implementation
│   └── resolution.py      # Resolution agent implementation
├── a2a_spec/
│   ├── a2a-spec.yaml      # Project config
│   ├── specs/
│   │   └── triage-to-resolution.yaml
│   ├── snapshots/
│   │   └── triage-agent/
│   │       └── billing_overcharge.json
│   ├── scenarios/
│   │   └── support_scenarios.yaml
│   └── adapters/
│       ├── __init__.py
│       ├── triage_adapter.py
│       └── resolution_adapter.py
└── tests/
    └── test_specs.py
```

## Walkthrough

### Step 1: Define the spec

The spec `triage-to-resolution.yaml` defines what the resolution agent expects from the triage agent:

- **Structural**: Must return `category`, `summary`, and `confidence` fields
- **Semantic**: Summary must faithfully reflect the customer's input
- **Policy**: Output must not contain PII

### Step 2: Create adapters

Adapters wrap your agents so a2a-spec can call them. See `adapters/triage_adapter.py` for an example.

### Step 3: Record snapshots

```bash
# From the customer_support directory:
a2aspec record --config a2a_spec/a2a-spec.yaml
```

This calls the live agents and saves their outputs as JSON snapshots.

### Step 4: Test in CI (replay mode)

```bash
a2aspec test --replay --config a2a_spec/a2a-spec.yaml
```

This validates the saved snapshots against the specs with zero LLM calls.

### Step 5: Detect drift

After changing a prompt or model:

```bash
a2aspec record   # Re-record with new prompt
a2aspec diff     # Compare new vs old outputs
```
