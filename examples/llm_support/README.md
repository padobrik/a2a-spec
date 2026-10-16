# LLM support example

Two agents, and the first one calls a real model:

1. **Triage agent** (`agents/triage.py`) sends the customer message to Claude and gets JSON back through structured output: `category`, `priority`, `summary` and `customer.sentiment` / `customer.wants_refund`.
2. **Resolution agent** (`agents/resolution.py`) is plain Python. It reads the triage fields and picks a queue, whether to escalate and whether to offer a refund.

agent-handshake calls the model once, when you record. After that the tests replay the snapshots, so they need no API key and give the same result every time.

## Run it

Run every command from `examples/llm_support`.

**1. Install.**

```bash
pip install -r requirements.txt
```

**2. Record the triage agent.** This is the only step that calls Claude (five short requests).

```bash
export ANTHROPIC_API_KEY=...
handshake record
```

The model is `claude-haiku-5-5`. Set `TRIAGE_MODEL` to use another one. The model name is the adapter version, so snapshots from different models do not mix.

**3. Make the contract from the resolution agent's code.**

```bash
handshake infer --producer triage-agent --consumer resolution-agent \
  --source agents/resolution.py:resolution_agent
```

The spec requires `category` because the code reads it with `ticket["category"]`. It also covers the nested fields `customer.sentiment` and `customer.wants_refund`, which the code reads with `.get()`.

**4. Test.** No API key is needed from here on.

```bash
handshake test
pytest --handshake handshake/specs
```

`handshake/specs/triage-quality.yaml` is written by hand. It adds rules that the consumer code cannot show: the summary must be at least 10 characters long (structural), and the output must not contain an internal ticket ID such as `INT-123456` (policy).

**5. Change the model or the prompt.** Edit `SYSTEM` in `agents/triage.py`, or set `TRIAGE_MODEL`, and record again:

```bash
handshake record
handshake diff
handshake test
```

`handshake diff` shows what the new output changed. `handshake test` fails if the change breaks what the resolution agent reads, for example if the new prompt makes the model drop `customer` or rename `category`.
