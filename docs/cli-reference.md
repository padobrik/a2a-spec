# CLI Reference

## `handshake init`

Initialize a new agent-handshake project with directory structure and example files.

```bash
handshake init [DIRECTORY] [--name NAME]
```

It also adds `__pycache__/` to `.gitignore`. An existing `.gitignore` is not
rewritten: only missing lines are added at the end.

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
the baseline. Exits 1 on high-severity drift or a deleted snapshot.

When specs exist for the producer, each change is rated by what the consumers
read. A removed field, or a field with a new type, that a spec names is `FAIL`
and names the consumer; for a spec made by `handshake infer` it also names the
file and line (from `read_at`). A change to a field that no spec names is
`INFO`, unless a spec sets `reads_unknown_keys`: then the change keeps its
structural rating. Without a spec, a removed field is `FAIL` and an added one
is `LOW`.

```bash
handshake diff [--agent NAME] [--base REF] [--config PATH]
```

## `handshake infer`

Generate a consumer-driven spec from the fields a consumer function reads.

```bash
handshake infer --producer ID --consumer ID --source FILE.py:FUNCTION [--name NAME] [--out PATH|-] [--force] [--allow-missing FIELD]...
handshake infer --check
```

If the consumer reads a field that the producer sent in no snapshot, the
command prints `FAIL`, writes no spec and exits 1. A broken producer is not
turned into an optional field. If the producer leaves the field out on
purpose, pass `--allow-missing FIELD` (a dotted path such as
`customer.tier`; repeat it for more fields): the field is then optional, the
command shows a `WARN` line, and the spec lists it under `allow_missing`.
`--check` accepts a `data["key"]` read of such a field, and its
"Regenerate" command repeats the flags.

The analysis follows helper functions in the same file that get the data
(up to three levels, methods through `self.` / `this.` included), list items
(`searches[].query`; the spec gets an array schema with `items`) and values
taken with `or`, `??` or a conditional.

The parameter that holds the producer's output is chosen by its type
(Pydantic, `TypedDict`, dataclass; TypeScript `interface`, `type` or Zod
schema), with the producer's snapshot keys deciding between several typed
parameters. If no parameter fits, the command exits 2 and names the
parameters it looked at. `--check` picks the parameter again from the spec's
own fields.

`--source` can also name a TypeScript or JavaScript function
(`agents/resolution.ts:resolutionAgent`) when the `typescript` extra is
installed. Function declarations, methods, and functions bound to a name
(`const resolutionAgent = async (ticket) => ...`) are found. Reading a missing
key in JavaScript gives `undefined`, so a key counts as read with `[]` only
when the code uses it without a fallback: `ticket.customer.tier` makes
`customer` strict, `ticket.customer?.tier` does not.

The generated spec records its consumer in `inferred_from` and the line numbers of each read in `read_at`.
When the command shows a `WARN` line about the consumer (for example
`data[key]`), the spec also gets `reads_unknown_keys: true`. `--check`
compares every such spec with the consumer's current code and exits 1 when
the code reads a field the spec does not cover, or reads with `data["key"]`
a field the spec makes optional, or reads keys it cannot name while the spec
does not set `reads_unknown_keys`. Nested reads such as
`data["customer"]["tier"]` are checked against the nested `properties` and
`required` of the spec. Fields the code no longer reads are
warnings. No snapshots are needed.

## `handshake skill`

Print the bundled agent skill, or install it as `DIR/agent-handshake/SKILL.md`.

```bash
handshake skill [--dir DIR] [--force]
```

## Exit codes

| Code | Meaning | Examples |
|---|---|---|
| `0` | Everything checked passed | All contracts hold; `diff` found no serious drift |
| `1` | A check found a problem | A contract is broken, `diff` found high-severity drift, `infer --check` found a spec that is out of date, an agent call failed |
| `2` | The command could not run as asked | Invalid `handshake.yaml` or spec, a broken snapshot file, a spec whose producer has no snapshots, no specs at all, a missing adapter |

When a run has both, the code is `2`: the run was not complete, so its passes cannot be trusted.

## Global Options

- `--version, -v` — Show version and exit
- `--help` — Show help
