<p align="center">
  <strong>agent-handshake</strong><br>
  <em>Contract tests for multi-agent systems</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/agent-handshake/"><img src="https://img.shields.io/pypi/v/agent-handshake?style=flat-square" alt="PyPI"></a>
  <a href="https://github.com/padobrik/agent-handshake/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/padobrik/agent-handshake/ci.yml?branch=main&style=flat-square&label=CI" alt="CI"></a>
  <a href="https://github.com/padobrik/agent-handshake/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?style=flat-square" alt="Python 3.11+">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/padobrik/agent-handshake/main/docs/demo.gif" alt="handshake infer generates a contract from the consumer's code; after a producer change, the hand-written spec passes and the inferred contract fails" width="760">
</p>

agent-handshake finds the fields that one agent reads from another agent. It tests these fields in CI. The tests use recorded outputs, so they make no LLM calls and need no API keys.

agent-handshake was called a2a-spec before version 0.7.

## The problem

Agent A sends data to agent B. You change the prompt of agent A, and its output changes. For example, agent A now sends `urgency` instead of `priority`.

Agent B reads `priority` with a default value. It does not stop with an error. It gives a wrong result, and no test fails.

## What agent-handshake does

1. It reads the code of agent B and finds the fields that agent B uses.
2. It records the output of agent A one time and saves it as JSON files in git.
3. It tests the recorded output against the fields that agent B needs. You run these tests in pytest or in CI.

<p align="center">
  <img src="https://raw.githubusercontent.com/padobrik/agent-handshake/main/docs/diagrams/how-it-works.svg" alt="handshake record saves the output of agent A as snapshots. handshake infer reads the code of agent B and writes a spec. handshake test or pytest tests the snapshots against the spec, with no LLM calls, and gives pass or fail." width="760">
</p>

## Terms

| Term | Meaning |
|---|---|
| Producer | The agent that sends the data. |
| Consumer | The agent that receives the data. |
| Spec | A YAML file. It gives the fields that the consumer needs from the producer. |
| Snapshot | A JSON file. It contains one recorded input and output of the producer. |
| Scenario | A named input for the producer. |
| Adapter | A small Python object. agent-handshake uses it to call your agent. |

## Get started

You need Python 3.11 or later and a git repository.

This example uses two agents. The producer `triage_agent` classifies a message. The consumer `resolution_agent` uses that result.

```python
# agents/triage.py
async def triage_agent(data: dict) -> dict:
    text = data["message"].lower()
    category = "billing" if "charge" in text else "general"
    return {"category": category, "priority": "high" if "urgent" in text else "low"}
```

```python
# agents/resolution.py
async def resolution_agent(ticket: dict) -> dict:
    escalate = ticket.get("priority", "low") == "high"
    return {"reply": f"We are checking your {ticket['category']} issue.", "escalate": escalate}
```

**1. Install agent-handshake.**

```bash
pip install agent-handshake
```

**2. Create the project files.**

```bash
handshake init
```

This command creates `handshake.yaml` and the `handshake/` directory.

**3. Remove the example spec and the example scenario.**

```bash
rm handshake/specs/example-spec.yaml handshake/scenarios/example-scenarios.yaml
```

**4. Add the producer to `handshake/adapters/__init__.py`.**

```python
from agent_handshake import FunctionAdapter
from agents.triage import triage_agent

ADAPTERS = {
    "triage-agent": FunctionAdapter(fn=triage_agent, agent_id="triage-agent", version="1.0"),
}
```

**5. Add inputs for the producer to `handshake/scenarios/support.yaml`.**

```yaml
scenarios:
  - name: double_charge
    input:
      message: "I was charged twice. This is urgent."
  - name: question
    input:
      message: "How do I change my address?"
```

**6. Record the output of the producer.**

```bash
handshake record
```

The command calls the producer one time for each scenario:

```
    PASS triage-agent / double_charge recorded
    PASS triage-agent / question recorded
[done] 2 snapshots saved to ./handshake/snapshots
```

If `ADAPTERS` has more than one agent, the command calls each agent with each scenario. To record one agent only, use `handshake record --agent triage-agent`. To give a scenario to some agents only, add `agents: [triage-agent]` to the scenario.

**7. Make the spec from the code of the consumer.**

```bash
handshake infer --producer triage-agent --consumer resolution-agent \
  --source agents/resolution.py:resolution_agent
```

The command writes `handshake/specs/triage-agent-to-resolution-agent.yaml`:

```yaml
# Generated by 'handshake infer' from agents/resolution.py:resolution_agent and 2 triage-agent snapshot(s). Review before committing.
#   priority: required, read at line 2
#   category: required, read at line 3
spec:
  name: triage-agent-to-resolution-agent
  producer: triage-agent
  consumer: resolution-agent
  structural:
    type: object
    required: [priority, category]
    properties:
      priority: {type: string}
      category: {type: string}
```

Read the spec before you commit it. If the command shows a `WARN` line, read [Limits](#limits).

**8. Run the tests.**

```bash
handshake test
```

```
PASS triage-agent-to-resolution-agent / double_charge
PASS triage-agent-to-resolution-agent / question
  2 passed  (total: 2)
```

**9. Commit the files.**

```bash
git add handshake.yaml agent_handshake agents
git commit -m "test: add agent contracts"
```

The committed snapshots are the baseline for the next steps.

## When you change an agent

<p align="center">
  <img src="https://raw.githubusercontent.com/padobrik/agent-handshake/main/docs/diagrams/change-workflow.svg" alt="Change the producer, then run handshake record, handshake diff and handshake test. If the tests pass, commit. If they fail and the change is not intended, fix the producer and record again. If the change is intended, update the consumer, run handshake infer --force and commit." width="760">
</p>

**1. Change the producer.** For example, change its prompt, its model or its code. In this example, the producer now sends `urgency` instead of `priority`.

**2. Record the output again.**

```bash
handshake record
```

**3. Compare the new output with the committed snapshots.**

```bash
handshake diff
```

```
  triage-agent / double_charge:
    FAIL priority: Field 'priority' was removed
    LOW  urgency: Field 'urgency' was added
```

**4. Run the tests.**

```bash
handshake test
```

```
FAIL triage-agent-to-resolution-agent / double_charge
    [<root>] 'priority' is a required property
```

**5. Correct the problem.**

- If the change in the producer is an error, correct the producer. Then do steps 2 to 4 again.
- If the change is necessary, change the consumer. Then run `handshake infer` with `--force` and commit the new spec and snapshots.

Do not record the snapshots again only to make a test pass. Do not delete snapshots or remove fields from a spec for this purpose.

## Keep the specs up to date

A consumer can start to read a new field when you change its code. Then its spec is not complete. To find this problem, run:

```bash
handshake infer --check
```

```
FAIL triage-agent-to-resolution-agent (agents/resolution.py:resolution_agent)
    resolution_agent reads 'language' (line 3), which the spec does not cover
```

The command compares each spec that `handshake infer` made with the current code of its consumer. It reads only code, so it needs no snapshots and makes no LLM calls. The output also shows the command that makes the spec again.

Add `handshake infer --check` to CI. The pytest plugin also runs this check as the `consumer_code` test of each inferred spec.

## Run the tests with pytest

agent-handshake has a pytest plugin. Add these lines to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
handshake_config = "handshake.yaml"
testpaths = ["tests", "handshake/specs"]
```

pytest then runs one test for each snapshot:

```
$ pytest -v
handshake/specs/triage-agent-to-resolution-agent.yaml::double_charge PASSED   [ 50%]
handshake/specs/triage-agent-to-resolution-agent.yaml::question PASSED        [100%]
```

The usual pytest options work, for example `-k`, `-x` and `--junitxml`. To run the tests one time without the configuration, use `pytest --handshake`.

To test a live output in your own test, use the `handshake_check` fixture. This example is an `async` test, so it needs an async plugin such as `pytest-asyncio`.

```python
async def test_triage_live(handshake_check):
    output = await triage_agent({"message": "I was charged twice"})
    handshake_check("triage-agent-to-resolution-agent", output)
```

## Run the tests in CI

The tests use the committed snapshots. CI needs no API keys.

On GitHub, use the agent-handshake action. It runs `handshake infer --check` and `handshake test`, and it shows each failure as an annotation in the pull request:

```yaml
# .github/workflows/contracts.yml
name: Agent contracts
on: [push, pull_request]

jobs:
  contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: padobrik/agent-handshake@v0.7.0
```

The action has these inputs: `package` (for example `agent-handshake[semantic]`), `working-directory`, `config`, `check-inferred` and `args`.

You can also run the commands yourself:

```yaml
# .github/workflows/contracts.yml
name: Agent contracts
on: [push, pull_request]

jobs:
  contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install agent-handshake
      - run: handshake infer --check
      - run: handshake test --format github
```

`--format github` shows each failure as an annotation in the pull request. For JUnit XML, use `--format junit > results.xml`. If your specs have semantic rules, install `agent-handshake[semantic]` instead.

## Write a spec by hand

A spec can have three types of rules:

| Rule type | What it finds | How |
|---|---|---|
| `structural` | A missing field, a wrong type, a value out of range | JSON Schema |
| `semantic` | A text field that no longer means the same thing | Similarity of local embeddings |
| `policy` | Text that must not occur, for example a card number | Regular expressions or your own function |

```yaml
spec:
  name: triage-to-resolution
  version: "1.0"
  producer: triage-agent
  consumer: resolution-agent
  structural:
    type: object
    required: [category]
    properties:
      category: {type: string, enum: [billing, general]}
  semantic:
    - rule: summary_matches_message
      method: embedding_similarity
      source_field: message     # field in the producer input
      target_field: summary     # field in the producer output
      threshold: 0.5
  policy:
    - rule: no_card_numbers
      method: regex
      patterns: ['\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b']
```

Semantic rules need `pip install "agent-handshake[semantic]"`. See [Writing specs](docs/writing-specs.md) for all options.

## Check exact values

A scenario can also give exact values for the output of an agent. `handshake test` and pytest compare these values with the snapshot or with the live output.

```yaml
scenarios:
  - name: double_charge
    input:
      message: "I was charged twice. This is urgent."
    expectations:
      triage-agent:
        category: billing
```

```
FAIL triage-agent-to-resolution-agent / double_charge
  expectations FAIL
    expected 'category' = 'billing', got 'general'
```

## Connect your agents

| Agent type | Adapter |
|---|---|
| Python `async` function | `FunctionAdapter(fn=..., agent_id=..., version=...)` |
| HTTP endpoint (POST JSON, receive JSON) | `HTTPAdapter(url=..., agent_id=..., version=...)` |
| LangChain runnable | `LangChainAdapter(runnable=..., agent_id=..., version=...)` (install `agent-handshake[langchain]`) |
| Agent with the [A2A protocol](https://a2a-protocol.org) 1.0 | `A2AAdapter(url=..., agent_id=...)` |

For an A2A agent, give the base URL of the agent. The adapter reads the Agent Card, finds the JSON-RPC interface and sends the scenario input. It records the agent version from the Agent Card in each snapshot.

```python
from agent_handshake import A2AAdapter

ADAPTERS = {
    "triage-agent": A2AAdapter(url="https://triage.example.com", agent_id="triage-agent"),
}
```

See [Writing adapters](docs/writing-adapters.md) for all options.

## Use with coding agents

agent-handshake contains an [Agent Skill](https://agentskills.io). The skill tells a coding agent how to use agent-handshake. It also tells the agent not to make a failed test pass by recording the snapshots again.

```bash
handshake skill --dir path/to/skills
```

This command writes `path/to/skills/agent-handshake/SKILL.md`. Export the skill again after you update agent-handshake.

## Limits

- `handshake infer` reads Python consumers. It finds `data["key"]`, `data.get("key")` and `"key" in data`, also in nested objects (`data["customer"]["tier"]`, `data.get("customer", {}).get("tier")`) and through a local name (`customer = data["customer"]`). It does not follow list items.
- `handshake infer` also reads TypeScript and JavaScript consumers (`.ts`, `.mts`, `.cts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`) after `pip install "agent-handshake[typescript]"`. It finds `data.key`, `data["key"]`, `data?.key`, `"key" in data` and destructuring (`const { key } = data`). The code is parsed, not run, so Node.js is not needed.
- If the consumer gives its input to another function, `handshake infer` cannot follow it. The command then shows a `WARN` line. Add the missing fields to the spec by hand.
- `handshake infer --check` checks only specs that contain `inferred_from`. Specs from agent-handshake 0.3 and earlier do not have it. Run `handshake infer` with `--force` again to add it.
- `handshake diff` compares with the snapshots in git. Commit the snapshots before you use it.
- `A2AAdapter` supports A2A 1.0 with JSON-RPC, with or without streaming. It does not support gRPC or HTTP+JSON.
- Semantic rules use a local embedding model. The `semantic` extra installs PyTorch.

## Commands

| Command | What it does |
|---|---|
| `handshake init` | Creates the project files. |
| `handshake record` | Calls the producers and saves their output as snapshots. |
| `handshake infer` | Makes a spec from the fields that a consumer reads. |
| `handshake infer --check` | Finds specs that do not cover what their consumer reads now. |
| `handshake test` | Tests the snapshots against the specs. |
| `handshake test --live` | Calls the producers with each scenario and tests their output. It saves nothing. |
| `handshake diff` | Compares the snapshots with the committed snapshots. |
| `handshake skill` | Exports the skill for coding agents. |

See [CLI reference](docs/cli-reference.md) for all options.

## Documentation

- [Writing specs](docs/writing-specs.md)
- [Writing adapters](docs/writing-adapters.md)
- [CLI reference](docs/cli-reference.md)
- [CI integration](docs/ci-integration.md)
- [Concepts](docs/concepts.md)
- [Architecture](docs/architecture.md)
- [Example project](examples/customer_support/)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0. See [LICENSE](LICENSE).
