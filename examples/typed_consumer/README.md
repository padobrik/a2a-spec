# Typed consumer example

The consumer gets the producer's output as a Pydantic model, next to other
parameters. `handshake infer` finds the parameter by its type and reads the
attributes the code uses.

- **Triage agent** (`agents/triage.py`) returns a dict: `category`, `priority`,
  `summary`. Plain Python, no model.
- **Resolution agent** (`agents/resolution.py`) is
  `resolution_agent(query: str, ticket: Ticket)`. `Ticket` is a Pydantic model
  in `agents/models.py`. The agent reads `ticket.category` and
  `getattr(ticket, "priority", "low")`.

## Run it

Run every command from `examples/typed_consumer`.

```bash
handshake record
handshake infer --producer triage-agent --consumer resolution-agent \
  --source agents/resolution.py:resolution_agent
handshake test
handshake infer --check
```

`infer` skips `query`, because a `str` cannot be the producer's output, and
takes `ticket`, because `Ticket` declares the producer's keys. The spec in
`handshake/specs/triage-agent-to-resolution-agent.yaml` has two fields:

- `category`, read at line 7 as `ticket.category`;
- `priority`, read at line 8 with `getattr(..., "low")`. It is still required:
  the producer sent it in every snapshot, and a missing value would turn every
  ticket into a low priority one without an error.

`summary` is not in the spec. The resolution agent does not read it, so the
producer may change it freely, and `handshake diff` rates such a change as
`INFO`.

If the code read a field that `Ticket` does not declare (`ticket.score`),
`infer` would print a `WARN` line with the line number, and a `FAIL` line,
because the producer never sends it.
