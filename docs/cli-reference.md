# CLI Reference

## `handshake init`

Initialize a new agent-handshake project with directory structure and example files.

```bash
handshake init [DIRECTORY] [--name NAME]
```

## `handshake record`

Record live agent outputs as snapshots by calling agents through adapters.

```bash
handshake record [--suite PATH] [--scenario NAME] [--agent ID]... [--config PATH]
```

`--suite` records only the scenarios in one file; `--scenario` records one
scenario by name; `--agent` records only the given agents from `ADAPTERS`
(repeat it for several). A scenario with an `agents` list is recorded only
for those agents, and `handshake test --live` calls only those agents with it:

```yaml
scenarios:
  - name: double_charge
    input:
      message: "I was charged twice."
    agents: [triage-agent]
```

## `handshake test`

Run spec validation against snapshots (replay) or live agents.

```bash
handshake test [--replay/--live] [--specs DIR] [--config PATH] [--format FORMAT] [--fail-fast]
```

`--live` calls each spec's producer through `ADAPTERS` with every scenario
and checks the live output; it saves no snapshots. A producer without an
adapter is skipped with a warning, and a failed agent call is a failed test.

`--format` is `console` (default), `github` (console output plus GitHub
Actions annotations), `markdown` or `junit` (only the report on stdout).

## `handshake diff`

Compare recorded snapshots against their committed version in git for
structural drift. Reports scenarios added (`NEW`) or deleted (`GONE`) since
the baseline. Exits 2 on high-severity drift or a deleted snapshot.

```bash
handshake diff [--agent NAME] [--base REF] [--config PATH]
```

## `handshake infer`

Generate a consumer-driven spec from the fields a consumer function reads.

```bash
handshake infer --producer ID --consumer ID --source FILE.py:FUNCTION [--name NAME] [--out PATH|-] [--force]
handshake infer --check
```

`--source` can also name a TypeScript or JavaScript function
(`agents/resolution.ts:resolutionAgent`) when the `typescript` extra is
installed. Function declarations, methods, and functions bound to a name
(`const resolutionAgent = async (ticket) => ...`) are found. Reading a missing
key in JavaScript gives `undefined`, so a key counts as read with `[]` only
when the code uses it without a fallback: `ticket.customer.tier` makes
`customer` strict, `ticket.customer?.tier` does not.

The generated spec records its consumer in `inferred_from`. `--check`
compares every such spec with the consumer's current code and exits 1 when
the code reads a field the spec does not cover, or reads with `data["key"]`
a field the spec makes optional. Nested reads such as
`data["customer"]["tier"]` are checked against the nested `properties` and
`required` of the spec. Fields the code no longer reads are
warnings. No snapshots are needed.

## `handshake skill`

Print the bundled agent skill, or install it as `DIR/agent-handshake/SKILL.md`.

```bash
handshake skill [--dir DIR] [--force]
```

## Global Options

- `--version, -v` — Show version and exit
- `--help` — Show help
