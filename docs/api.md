# Python API

The CLI and the pytest plugin use two functions. Use them to check contracts
from your own code or from another tool.

```python
from agent_handshake import check, load_snapshots, load_spec

spec = load_spec("handshake/specs/triage-to-resolution.yaml")
result = check(spec, load_snapshots("handshake/snapshots"))

if not result.passed:
    for error in result.errors:
        print(error)
    for case in result.failed:
        print(case.snapshot.scenario, case.failures)
```

The same snapshots and spec always give the same result. Nothing calls a
model or the network.

## `load_snapshots(source) -> list[Snapshot]`

Reads recorded snapshots.

- `source` is a snapshot file, an agent directory (`handshake/snapshots/triage-agent`)
  or the snapshots directory (`handshake/snapshots`). Directories are searched
  for `*.json` files, also in subdirectories.
- The list is sorted by agent, scenario and file name.
- Raises `ConfigError` if `source` does not exist, and `SnapshotFormatError` if a
  file is not a valid snapshot. The message names the file and says what is wrong.

A `Snapshot` has `fingerprint.agent_id`, `scenario`, `input_data`, `output_data`,
`timestamp` and `metadata`.

## `check(spec, snapshots, expected=None) -> CheckResult`

Checks the snapshots of `spec.producer` against `spec`. Snapshots of other agents
are ignored, so you can pass all snapshots of a project.

- `expected` maps a scenario name to exact output values, for example
  `{"double_charge": {"category": "billing"}}`. This is what `expectations` in
  scenario files does.
- No snapshots for the producer is an error in the result, not a pass.

### `CheckResult`

| Attribute | Meaning |
|---|---|
| `spec` | The spec that was checked |
| `cases` | One `SnapshotResult` per snapshot of the producer |
| `errors` | Problems with the input, for example no snapshots for the producer |
| `passed` | `True` when there are no errors and every case passed |
| `failed` | The cases that did not pass |

### `SnapshotResult`

| Attribute | Meaning |
|---|---|
| `snapshot` | The snapshot that was checked |
| `check` | The detailed result: `structural`, `policy` and `expectations` |
| `passed` | `True` when every rule passed |
| `failures` | One line per problem, for example `structural: [<root>] 'category' is a required property` |
