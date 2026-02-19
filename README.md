<p align="center">
  <strong>a2a-spec</strong><br>
  <em>The open specification for testing, validating, and guaranteeing agent-to-agent interactions.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/a2a-spec/"><img src="https://img.shields.io/pypi/v/a2a-spec?style=flat-square" alt="PyPI"></a>
  <a href="https://github.com/padobrik/a2a-spec/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/padobrik/a2a-spec/ci.yml?branch=main&style=flat-square&label=CI" alt="CI"></a>
  <a href="https://github.com/padobrik/a2a-spec/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?style=flat-square" alt="Python 3.11+">
  <a href="https://github.com/padobrik/a2a-spec"><img src="https://img.shields.io/badge/typed-PEP%20561-brightgreen?style=flat-square" alt="Typed"></a>
</p>

---

## Problem

Multi-agent AI systems are **impossible to test reliably** with conventional tools.

Here is a concrete example of what goes wrong: you refine a prompt in your triage agent. The agent starts returning `issue_type` instead of `category`. Your resolution agent silently receives `None` for a key field and produces garbage output. No test caught it. Three hours later you find out from a user complaint.

The root causes are systemic:

- **LLM outputs are non-deterministic** — you cannot diff two live runs and call it a test.
- **Agent contracts are implicit** — there is no formal definition of what Agent B expects from Agent A.
- **Semantic drift is invisible to schemas** — a field can stay `string` while its meaning completely changes.
- **CI is too expensive to run live** — calling LLMs on every push is slow and costs real money.

Existing tools focus on prompt evaluation or observability. None provide **contract testing between agents**.

---

## Solution

**a2a-spec** is a specification, testing, and validation layer for multi-agent systems. You define what one agent expects from another as a YAML spec. You record LLM outputs as snapshots once. You replay them deterministically in CI with zero LLM calls. You detect structural and semantic regressions before they reach production.

```
Agent A ──[spec]──> Agent B ──[spec]──> Agent C
    │                   │                   │
    └── snapshot ──> replay ──> validate ──> ✓ CI passes
```

---

## Comparison

| a2a-spec is **not** | Examples | What a2a-spec **is** |
|---|---|---|
| An agent framework | LangChain, CrewAI, AutoGen | A **testing layer** that sits alongside any framework |
| An observability tool | LangSmith, Arize, Langfuse | A **validation engine** that runs in CI, not production |
| A prompt evaluation tool | Promptfoo, DeepEval | A **contract testing** system between agents |
| An agent runtime | n/a | A **specification framework** for agent boundaries |

---

## How It Works

a2a-spec follows a **record-once, replay-forever** workflow:

**1. Write a spec** — a YAML file that defines the contract between two agents: what fields are required, what they mean, and what is forbidden.

**2. Record snapshots locally** — run `a2aspec record` with your API keys. It calls your live agents and saves each output as a JSON file.

**3. Commit snapshots to git** — the JSON files become your test baselines. They are version-controlled, reviewable in PRs, and act as a precise record of what your agents actually produce.

**4. Validate in CI** — run `a2aspec test --replay`. It loads the snapshots and validates them against the specs. No API keys. No LLM calls. Runs in milliseconds.

**5. Detect drift when prompts change** — after modifying a prompt or upgrading a model, run `a2aspec record` again, then `a2aspec diff`. The diff engine reports exactly what changed structurally and semantically before you merge.

---

## Quick Start

### Install

```bash
pip install a2a-spec
```

With optional features:

```bash
pip install a2a-spec[semantic]    # Embedding-based semantic comparison
pip install a2a-spec[langchain]   # LangChain adapter
pip install a2a-spec[dev]         # Testing and linting tools
pip install a2a-spec[all]         # Everything
```

### Initialize a project

```bash
a2aspec init --name my-project
```

This creates:
```
my-project/
├── a2a-spec.yaml              # Project configuration
└── a2a_spec/
    ├── specs/                  # Agent-to-agent contracts
    │   └── example-spec.yaml
    ├── snapshots/              # Recorded outputs (committed to git!)
    ├── scenarios/              # Test input scenarios
    └── adapters/               # Agent wrappers
```

### Define a spec

A spec is a YAML contract between a **producer** agent and a **consumer** agent. It defines what the consumer expects across three validation layers:

```yaml
# a2a_spec/specs/triage-to-resolution.yaml
spec:
  name: triage-to-resolution
  version: "1.0"
  producer: triage-agent
  consumer: resolution-agent
  description: "What the resolution agent expects from triage"

  structural:
    type: object
    required: [category, summary, confidence]
    properties:
      category:
        type: string
        enum: [billing, shipping, product, general]
      summary:
        type: string
        minLength: 10
        maxLength: 500
      confidence:
        type: number
        minimum: 0.0
        maximum: 1.0

  semantic:
    - rule: summary_reflects_input
      description: "Summary must faithfully reflect the customer message"
      method: embedding_similarity
      threshold: 0.8

  policy:
    - rule: no_pii
      description: "Output must not contain PII"
      method: regex
      patterns:
        - '\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'  # Credit card
        - '\b\d{3}-\d{2}-\d{4}\b'                       # SSN
```

### Record snapshots

```bash
a2aspec record  # Calls live agents via adapters, saves outputs to disk
```

Each recorded output becomes a JSON file committed to git — your deterministic test baseline:

```json
{
  "fingerprint": "a1b2c3d4e5f6",
  "agent_id": "triage-agent",
  "scenario": "billing_overcharge",
  "input": { "message": "I was charged twice for my order #12345" },
  "output": {
    "category": "billing",
    "summary": "Customer reports a duplicate charge on order #12345",
    "confidence": 0.92
  }
}
```

### Test in CI (zero LLM calls)

```bash
a2aspec test --replay  # Validates saved snapshots against specs
```

```
 PASS  triage-agent :: billing_overcharge    structural ✓  semantic ✓  policy ✓
 PASS  triage-agent :: shipping_delay        structural ✓  semantic ✓  policy ✓
 FAIL  triage-agent :: product_defect        structural ✗  field 'confidence' missing
```

No API keys needed. No LLM costs. Fully deterministic. Runs in milliseconds.

### Detect semantic drift

After changing a prompt or upgrading a model:

```bash
a2aspec record   # Re-record with the new configuration
a2aspec diff     # Compare new outputs against the committed baseline
```

```
triage-agent :: billing_overcharge
  summary   MEDIUM  semantic similarity 0.71 (threshold 0.85)
             was: "Customer reports a duplicate charge on order #12345"
             now: "Billing issue: duplicate charge"
  category  NONE    unchanged
```

The diff engine reports structural changes (fields added/removed/type-changed) and semantic drift (meaning shifted beyond threshold), with severity levels from LOW to CRITICAL.

---

## Core Concepts

### Three Validation Layers

Every spec can define three independent layers of validation. Each catches a different class of regression:

| Layer | What it catches | How |
|-------|----------------|-----|
| **Structural** | Field missing, wrong type, value out of range | JSON Schema |
| **Semantic** | Meaning drifted even though the field is still present | Embedding similarity |
| **Policy** | Hard rules violated — PII leaked, forbidden pattern present | Regex or custom function |

You need all three because they are not redundant. A summary field can remain a non-empty string (structural pass) while its meaning silently changes (semantic fail). A field can satisfy both structural and semantic rules while still leaking a credit card number (policy fail).

### Concepts Glossary

| Concept | Description |
|---------|-------------|
| **Spec** | A YAML file defining what one agent expects from another — structure, semantics, and policy rules |
| **Snapshot** | A recorded LLM output for a given input, stored as JSON and committed to git |
| **Replay** | Running validation against saved snapshots with zero LLM calls — fast, free, deterministic |
| **Diff** | Structural + semantic comparison between old and new agent outputs, with severity levels |
| **Pipeline** | A DAG of agents with routing conditions, tested end-to-end with spec validation at each step |
| **Adapter** | A wrapper around your agent (function, HTTP, LangChain) so a2a-spec can call it |

→ See [docs/concepts.md](docs/concepts.md) for detailed explanations.

---

## Adapters — Wrap Any Agent

a2a-spec is **framework-agnostic**. Adapters wrap your agents so the framework can call them during recording and testing.

### Plain async functions

```python
from a2a_spec import FunctionAdapter

async def my_triage_agent(input_data: dict) -> dict:
    # Your agent logic (calls OpenAI, Anthropic, local model, etc.)
    return {"category": "billing", "summary": "Customer reports duplicate charge", "confidence": 0.95}

adapter = FunctionAdapter(
    fn=my_triage_agent,
    agent_id="triage-agent",
    version="1.0.0",
    model="gpt-4",
)
```

### HTTP endpoints

```python
from a2a_spec import HTTPAdapter

adapter = HTTPAdapter(
    url="http://localhost:8000/triage",
    agent_id="triage-agent",
    version="1.0.0",
    headers={"Authorization": "Bearer $TOKEN"},
    timeout=30.0,
)
```

### LangChain runnables

```python
from a2a_spec import LangChainAdapter
from langchain_core.runnables import RunnableLambda

chain = RunnableLambda(lambda x: {"category": "billing", "summary": x["message"], "confidence": 0.9})

adapter = LangChainAdapter(
    runnable=chain,
    agent_id="triage-agent",
    version="1.0.0",
)
```

### Custom adapters

```python
from a2a_spec import AgentAdapter, AgentMetadata, AgentResponse

class MyCrewAIAdapter(AgentAdapter):
    def get_metadata(self) -> AgentMetadata:
        return AgentMetadata(agent_id="my-crew-agent", version="1.0")

    async def call(self, input_data: dict) -> AgentResponse:
        result = await my_crew.kickoff(input_data)
        return AgentResponse(output=result.dict())
```

→ See [docs/writing-adapters.md](docs/writing-adapters.md) for the full guide.

---

## Pipeline Testing

Test entire multi-agent pipelines as a DAG. a2a-spec validates each agent's output against its spec and checks routing conditions:

```yaml
pipeline:
  name: customer-support
  agents:
    triage-agent: {}
    billing-agent: {}
    shipping-agent: {}
    resolution-agent: {}
  edges:
    - from: triage-agent
      to: billing-agent
      condition: "output.category == 'billing'"
    - from: triage-agent
      to: shipping-agent
      condition: "output.category == 'shipping'"
    - from: [billing-agent, shipping-agent]
      to: resolution-agent
  test_cases:
    - name: billing_flow
      input: { message: "I was charged twice" }
```

```bash
a2aspec pipeline test pipeline.yaml --mode replay
```

Routing conditions use a safe AST-based evaluator — no `eval()` involved.

→ See [docs/architecture.md](docs/architecture.md) for the pipeline execution model.

---

## Configuration

Project configuration lives in `a2a-spec.yaml`:

```yaml
project_name: "my-project"
version: "1.0"

specs_dir: "./a2a_spec/specs"
scenarios_dir: "./a2a_spec/scenarios"

semantic:
  provider: sentence-transformers
  model: all-MiniLM-L6-v2     # Lazy-loaded, only when needed
  enabled: true

storage:
  backend: local
  path: ./a2a_spec/snapshots

ci:
  fail_on_semantic_drift: true
  drift_threshold: 0.15
  replay_mode: exact
```

---

## Python API

Use a2a-spec programmatically in your existing test suite:

```python
from a2a_spec import load_spec, validate_output, SnapshotStore, ReplayEngine

# Load a spec and validate an output dict against it
spec = load_spec("a2a_spec/specs/triage-to-resolution.yaml")
result = validate_output(
    {"category": "billing", "summary": "Customer charged twice", "confidence": 0.95},
    spec,
)
assert result.passed, result.errors

# Replay a recorded snapshot (no LLM call)
store = SnapshotStore("./a2a_spec/snapshots")
engine = ReplayEngine(store)
output = engine.replay("triage-agent", "billing_overcharge")

# Diff two outputs structurally and semantically
from a2a_spec import DiffEngine
diff = DiffEngine()
results = diff.diff(old_output, new_output, semantic_threshold=0.85)
for r in results:
    print(f"{r.field}: {r.severity} — {r.explanation}")

# Register and run a custom policy validator
from a2a_spec.policy.engine import PolicyEngine
engine = PolicyEngine()
engine.register_validator("no_pii", lambda output, input_data: "ssn" not in str(output))
```

### pytest integration

```python
import pytest
from a2a_spec import load_spec, validate_output, ReplayEngine, SnapshotStore

@pytest.fixture
def replay_engine():
    store = SnapshotStore("./a2a_spec/snapshots")
    return ReplayEngine(store)

@pytest.mark.parametrize("scenario", ["billing_overcharge", "shipping_delay", "product_defect"])
def test_triage_spec(replay_engine, scenario):
    spec = load_spec("a2a_spec/specs/triage-to-resolution.yaml")
    output = replay_engine.replay("triage-agent", scenario)
    result = validate_output(output, spec)
    assert result.passed, f"Spec violations in {scenario}: {result.errors}"
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `a2aspec init [DIR]` | Scaffold a new a2a-spec project with examples |
| `a2aspec record` | Record live agent outputs as snapshots |
| `a2aspec test --replay` | Validate snapshots against specs (deterministic, zero LLM calls) |
| `a2aspec test --live` | Validate live agent outputs against specs |
| `a2aspec diff` | Compare current outputs against baselines |
| `a2aspec diff --agent NAME` | Diff a specific agent only |
| `a2aspec pipeline test FILE` | Test a multi-agent pipeline DAG |
| `a2aspec --version` | Show version |

→ See [docs/cli-reference.md](docs/cli-reference.md) for full options and flags.

---

## CI Integration

a2a-spec is designed for CI-first workflows. Record locally with your API keys; test in CI against committed snapshots — no secrets required in CI.

```yaml
# .github/workflows/a2a-spec.yml
name: Agent Contract Tests
on: [push, pull_request]

jobs:
  spec-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install a2a-spec
      - run: a2aspec test --replay
```

**Output formats:**

| Format | Flag | Use Case |
|---|---|---|
| Console (Rich) | `--format console` | Local development |
| Markdown | `--format markdown` | PR comments |
| JUnit XML | `--format junit` | CI test reporters |
| GitHub Annotations | `--format github` | Inline PR annotations |

→ See [docs/ci-integration.md](docs/ci-integration.md) for GitHub Actions, Jenkins, and more.

---

## Comparison

| Feature | a2a-spec | Pact | DeepEval | Promptfoo | LangSmith |
|---------|----------|------|----------|-----------|-----------|
| Agent-to-agent contracts | ✅ | ✅ | ❌ | ❌ | ❌ |
| LLM output snapshots | ✅ | ❌ | ❌ | ❌ | ❌ |
| Deterministic CI replay | ✅ | ✅ | ❌ | ❌ | ❌ |
| Semantic drift detection | ✅ | ❌ | ✅ | ✅ | ✅ |
| Policy enforcement (PII, etc.) | ✅ | ❌ | ✅ | ✅ | ❌ |
| Pipeline DAG testing | ✅ | ❌ | ❌ | ❌ | ❌ |
| Framework agnostic | ✅ | ✅ | ❌ | ❌ | ❌ |
| Zero LLM calls in CI | ✅ | N/A | ❌ | ❌ | ❌ |
| Typed Python API (PEP 561) | ✅ | N/A | ✅ | N/A | ✅ |

---

## Architecture

```
src/a2a_spec/
├── cli/          # Typer CLI (init, record, test, diff, pipeline)
├── spec/         # Spec schema (Pydantic), YAML loader, JSON Schema validator
├── snapshot/     # Record, store, fingerprint, and replay engine
├── diff/         # Structural (JSON) + semantic (embedding) comparison
├── pipeline/     # DAG builder, topological executor, execution traces
├── adapters/     # Agent wrappers: function, HTTP, LangChain
├── policy/       # Policy engine with regex and custom validators
├── semantic/     # Embedding model interface (sentence-transformers)
├── reporting/    # Console (Rich), Markdown, JUnit XML, GitHub annotations
├── config/       # YAML config loader with Pydantic validation
├── _internal/    # SHA256 hashing, safe expression evaluator, type aliases
└── exceptions.py # Hierarchical error types with actionable messages
```

→ See [docs/architecture.md](docs/architecture.md) for the full design.

---

## Examples

The [`examples/customer_support/`](examples/customer_support/) directory contains a complete walkthrough:

- Two agents (triage + resolution) with a2a-spec contract
- YAML spec with structural, semantic, and policy rules
- Pre-recorded snapshot for deterministic replay
- Test scenarios and pytest integration
- Step-by-step README

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation and first test in 2 minutes |
| [Core Concepts](docs/concepts.md) | Specs, snapshots, replay, diff explained |
| [CLI Reference](docs/cli-reference.md) | Every command with all options |
| [Writing Specs](docs/writing-specs.md) | Structural, semantic, and policy rules |
| [Writing Adapters](docs/writing-adapters.md) | Wrap any agent for a2a-spec |
| [CI Integration](docs/ci-integration.md) | GitHub Actions, JUnit, exit codes |
| [Architecture](docs/architecture.md) | Module design and extension points |

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, check commands, and PR process.

---

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
