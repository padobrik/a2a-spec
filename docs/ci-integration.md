# CI Integration

## GitHub Actions

```yaml
name: a2a-spec Tests
on: [push, pull_request]

jobs:
  spec-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install a2a-spec
      - run: a2aspec test --replay --format junit > results.xml
      - uses: mikepenz/action-junit-report@v4
        if: always()
        with:
          report_paths: results.xml
```

## Key Principles

1. **Always use replay mode in CI** — no LLM calls, no API keys needed
2. **Commit snapshots to git** — they are your test baselines
3. **Record locally, test in CI** — developers record, CI replays
4. **Fail on semantic drift** — catch regressions before merge

## Output Formats

| Format | Flag | Use Case |
|--------|------|----------|
| Console | `--format console` | Local development |
| Markdown | `--format markdown` | PR comments |
| JUnit XML | `--format junit` | CI systems |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All tests passed |
| 1 | One or more tests failed |
| 2 | Semantic drift above threshold |
