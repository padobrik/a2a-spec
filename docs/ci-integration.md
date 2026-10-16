# CI integration

The tests use the committed snapshots, so CI needs no API keys and makes no
LLM calls. Record snapshots on your machine, commit them, and run the tests
in CI.

## GitHub Action

```yaml
steps:
  - uses: actions/checkout@v6
  - uses: padobrik/agent-handshake@v0.8.0
    with:
      package: agent-handshake[semantic]          # pip requirement to install
      working-directory: services/agents   # where handshake.yaml is
      config: handshake.yaml                # optional
      check-inferred: "true"               # run handshake infer --check
      args: --fail-fast                    # extra flags for handshake test
```

The output `test-exit-code` is the exit code of `handshake test`: `0` when every contract passed, `1` when one failed, empty when the step did not run (for example, the installation failed). Use it with `continue-on-error: true` to act on the result in a later step.

All inputs are optional. Annotations point at the spec files relative to the
repository root.

## GitHub Actions without the action

```yaml
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
      - run: handshake test --format github
```

`--format github` prints the usual output and one annotation for each
failure, so the pull request shows the failure on the spec file.

## JUnit XML

To give the results to a test report tool, write JUnit XML:

```bash
handshake test --format junit > results.xml
```

`pytest --junitxml=results.xml` gives the same result when you use the
pytest plugin.

## Output formats

| Format | Flag | Output |
|--------|------|--------|
| Console | `--format console` (default) | Results for people, on stdout |
| GitHub | `--format github` | Console output plus GitHub Actions annotations |
| Markdown | `--format markdown` | Only a Markdown report on stdout, for example for a PR comment |
| JUnit XML | `--format junit` | Only JUnit XML on stdout |

With `markdown` and `junit`, warnings go to stderr, so you can redirect stdout
to a file.

## Exit codes

| Command | Code | Meaning |
|---------|------|---------|
| `handshake test` | 0 | All tests passed |
| `handshake test` | 1 | One or more tests failed, or the configuration is not valid |
| `handshake diff` | 2 | High-severity drift or a deleted snapshot (with `ci.fail_on_semantic_drift`) |
