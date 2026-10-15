---
name: a2a-spec
description: Keep agent-to-agent contracts green with a2a-spec. Use when a project has an a2a-spec.yaml and you change an agent's prompt, model, output fields or the code that reads another agent's output, add a new agent or agent-to-agent edge, or a2a-spec checks fail in tests or CI.
---

# a2a-spec

a2a-spec checks that each agent still gives the next agent what it needs.
Contracts (specs) live under `specs_dir`, recorded agent outputs (snapshots)
under `storage.path`, both set in `a2a-spec.yaml`. Snapshots are the test
baseline and are committed to git.

## The one rule

A failing contract is a finding, not an obstacle. Never make it pass by:

- re-recording snapshots without showing the user `a2aspec diff` output first;
- deleting snapshots or specs, or removing fields from `required`;
- lowering a semantic `threshold` or adding `--no-semantic` / `--a2a-no-semantic`;
- editing a snapshot JSON by hand.

If the contract change is intended, say so, change the consumer first, then
regenerate the contract (see "Adding or changing an edge").

## Before you change an agent

Run the current contracts so you know the baseline:

```bash
a2aspec test
a2aspec infer --check
```

If the project enables the pytest plugin (`a2a_config` in the pytest ini
options), `pytest` runs the same checks; `pytest --a2a` works without it.

## After changing a producer (prompt, model, output shape)

1. Ask the user before recording: `a2aspec record` calls live agents and may
   cost money. Record one scenario with `--scenario NAME` when possible.
2. Show what changed against the committed snapshots (`--base REF` to compare
   with another revision):

   ```bash
   a2aspec diff --agent PRODUCER
   ```

   `NEW` lines are scenarios not committed yet; `GONE` lines are committed
   snapshots that no longer exist and must be explained or restored.

3. Validate the new snapshots against every contract:

   ```bash
   a2aspec test
   ```

4. Report the diff and test output to the user. If a contract fails, fix the
   producer, or follow "Adding or changing an edge" if the consumer should
   change too.

Without permission to call live agents, stop after step 1 and tell the user
which scenarios need re-recording.

## After changing a consumer

Run `a2aspec infer --check`. A `FAIL` means the consumer now reads a field
its spec does not cover. Regenerate the spec with the command the output
prints, review the YAML diff, and run `a2aspec test`.

## Adding or changing an edge

When an agent starts reading another agent's output, or the code that reads it
changes, regenerate the consumer-driven contract from code:

```bash
a2aspec infer --producer PRODUCER --consumer CONSUMER \
  --source path/to/consumer.py:function --force
```

- Review every `WARN` line. "never sent it" means the consumer reads a field
  the producer does not produce: that is a bug in one of them, not in the spec.
  "used as a whole" or "non-literal key" means the analyzer could not see all
  reads; add the missing fields to the spec by hand.
- Show the user the YAML diff (`git diff` on the spec) before committing.
- Run `a2aspec test` afterwards.

## Checking live output in tests

Inside the user's tests, validate an agent's real output against a contract
with the pytest fixture:

```python
async def test_triage(a2a_check):
    output = await triage_agent({"message": "charged twice"})
    a2a_check("triage-to-resolution", output, {"message": "charged twice"})
```

## Reading failures

- `structural: [<root>] 'X' is a required property` — the producer stopped
  sending `X`, or renamed it. The consumer would get a missing value.
- `structural: [X] ...` — `X` has the wrong type or value.
- `policy RULE: Pattern matched in field 'X'` — forbidden content such as PII.
- `semantic RULE: similarity S < threshold T` — the text no longer means what
  it should. Compare the snapshot input and output before touching anything.
- `a2aspec diff` exits 2 — high-severity drift or a deleted snapshot; read the
  report before re-recording anything.
- `sentence-transformers is required` — install `a2a-spec[semantic]`; do not
  disable semantic checks instead.
