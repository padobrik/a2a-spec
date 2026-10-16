---
name: agent-handshake
description: Keep agent-to-agent contracts green with agent-handshake. Use when a project has a handshake.yaml and you change an agent's prompt, model, output fields or the code that reads another agent's output, add a new agent or agent-to-agent edge, or agent-handshake checks fail in tests or CI.
---

# agent-handshake

agent-handshake checks that each agent still gives the next agent what it needs.
Contracts (specs) live under `specs_dir`, recorded agent outputs (snapshots)
under `storage.path`, both set in `handshake.yaml`. Snapshots are the test
baseline and are committed to git.

## The one rule

A failing contract is a finding, not an obstacle. Never make it pass by:

- re-recording snapshots without showing the user `handshake diff` output first;
- deleting snapshots or specs, or removing fields from `required`;
- lowering a semantic `threshold` or adding `--no-semantic` / `--handshake-no-semantic`;
- editing a snapshot JSON by hand.

If the contract change is intended, say so, change the consumer first, then
regenerate the contract (see "Adding or changing an edge").

## Before you change an agent

Run the current contracts so you know the baseline:

```bash
handshake test
handshake infer --check
```

If the project enables the pytest plugin (`handshake_config` in the pytest ini
options), `pytest` runs the same checks; `pytest --handshake` works without it.

## After changing a producer (prompt, model, output shape)

1. Ask the user before recording: `handshake record` calls live agents and may
   cost money. Record one scenario with `--scenario NAME` when possible.
2. Show what changed against the committed snapshots (`--base REF` to compare
   with another revision):

   ```bash
   handshake diff --agent PRODUCER
   ```

   `NEW` lines are scenarios not committed yet; `GONE` lines are committed
   snapshots that no longer exist and must be explained or restored.

3. Validate the new snapshots against every contract:

   ```bash
   handshake test
   ```

4. Report the diff and test output to the user. If a contract fails, fix the
   producer, or follow "Adding or changing an edge" if the consumer should
   change too.

Without permission to call live agents, stop after step 1 and tell the user
which scenarios need re-recording.

## After changing a consumer

Run `handshake infer --check`. A `FAIL` means the consumer now reads a field
its spec does not cover. Regenerate the spec with the command the output
prints, review the YAML diff, and run `handshake test`.

## Adding or changing an edge

When an agent starts reading another agent's output, or the code that reads it
changes, regenerate the consumer-driven contract from code:

```bash
handshake infer --producer PRODUCER --consumer CONSUMER \
  --source path/to/consumer.py:function --force
```

- Review every `WARN` line. "never sent it" means the consumer reads a field
  the producer does not produce: that is a bug in one of them, not in the spec.
  "used as a whole" or "non-literal key" means the analyzer could not see all
  reads; add the missing fields to the spec by hand.
- Show the user the YAML diff (`git diff` on the spec) before committing.
- Run `handshake test` afterwards.

## Checking live output in tests

Inside the user's tests, validate an agent's real output against a contract
with the pytest fixture:

```python
async def test_triage(handshake_check):
    output = await triage_agent({"message": "charged twice"})
    handshake_check("triage-to-resolution", output, {"message": "charged twice"})
```

## Reading failures

- `structural: [<root>] 'X' is a required property` — the producer stopped
  sending `X`, or renamed it. The consumer would get a missing value.
- `structural: [X] ...` — `X` has the wrong type or value.
- `policy RULE: Pattern matched in field 'X'` — forbidden content such as PII.
- `semantic RULE: similarity S < threshold T` — the text no longer means what
  it should. Compare the snapshot input and output before touching anything.
- `handshake diff` exits 2 — high-severity drift or a deleted snapshot; read the
  report before re-recording anything.
- `sentence-transformers is required` — install `agent-handshake[semantic]`; do not
  disable semantic checks instead.
