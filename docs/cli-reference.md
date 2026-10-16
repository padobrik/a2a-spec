# CLI Reference

## `a2aspec init`

Initialize a new a2a-spec project with directory structure and example files.

```bash
a2aspec init [DIRECTORY] [--name NAME]
```

## `a2aspec record`

Record live agent outputs as snapshots by calling agents through adapters.

```bash
a2aspec record [--suite PATH] [--scenario NAME] [--config PATH]
```

`--suite` records only the scenarios in one file; `--scenario` records one
scenario by name.

## `a2aspec test`

Run spec validation against snapshots (replay) or live agents.

```bash
a2aspec test [--replay/--live] [--specs DIR] [--config PATH] [--format FORMAT] [--fail-fast] [--no-semantic]
```

`--live` calls each spec's producer through `ADAPTERS` with every scenario
and checks the live output; it saves no snapshots. A producer without an
adapter is skipped with a warning, and a failed agent call is a failed test.

`--format` is `console` (default), `github` (console output plus GitHub
Actions annotations), `markdown` or `junit` (only the report on stdout).

## `a2aspec diff`

Compare recorded snapshots against their committed version in git for
structural and semantic drift. Reports scenarios added (`NEW`) or deleted
(`GONE`) since the baseline. Exits 2 on high-severity drift or a deleted
snapshot when `ci.fail_on_semantic_drift` is true.

```bash
a2aspec diff [--agent NAME] [--base REF] [--threshold FLOAT] [--config PATH]
```

## `a2aspec infer`

Generate a consumer-driven spec from the fields a consumer function reads.

```bash
a2aspec infer --producer ID --consumer ID --source FILE.py:FUNCTION [--name NAME] [--out PATH|-] [--force]
a2aspec infer --check
```

The generated spec records its consumer in `inferred_from`. `--check`
compares every such spec with the consumer's current code and exits 1 when
the code reads a field the spec does not cover, or reads with `data["key"]`
a field the spec makes optional. Nested reads such as
`data["customer"]["tier"]` are checked against the nested `properties` and
`required` of the spec. Fields the code no longer reads are
warnings. No snapshots are needed.

## `a2aspec skill`

Print the bundled agent skill, or install it as `DIR/a2a-spec/SKILL.md`.

```bash
a2aspec skill [--dir DIR] [--force]
```

## `a2aspec pipeline test`

Test a pipeline DAG definition, validating each agent against specs.

```bash
a2aspec pipeline test PIPELINE_FILE [--scenario NAME] [--mode replay|live] [--config PATH]
```

`--mode replay` uses each agent's snapshot for the test case name; `--mode
live` calls the agents in `ADAPTERS`. Each step is checked against the
structural rules of the specs where that agent is the producer.

## Global Options

- `--version, -v` — Show version and exit
- `--help` — Show help
