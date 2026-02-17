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

## `a2aspec test`

Run spec validation against snapshots (replay) or live agents.

```bash
a2aspec test [--replay/--live] [--specs DIR] [--config PATH] [--format FORMAT] [--fail-fast]
```

## `a2aspec diff`

Compare current snapshots against previous baselines for structural and semantic drift.

```bash
a2aspec diff [--agent NAME] [--threshold FLOAT] [--config PATH]
```

## `a2aspec pipeline test`

Test a pipeline DAG definition, validating each agent against specs.

```bash
a2aspec pipeline test PIPELINE_FILE [--scenario NAME] [--mode replay|live] [--config PATH]
```

## Global Options

- `--version, -v` — Show version and exit
- `--help` — Show help
