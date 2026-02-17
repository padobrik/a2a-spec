# Architecture

## Package Structure

```
src/a2a_spec/
├── cli/          # Typer CLI commands
├── spec/         # Spec schema, loading, validation
├── snapshot/     # Record and replay engine
├── diff/         # Structural + semantic comparison
├── pipeline/     # DAG builder and executor
├── adapters/     # Agent wrappers (function, HTTP, LangChain)
├── policy/       # Policy enforcement engine
├── semantic/     # Embedding model interface
├── reporting/    # Console, Markdown, JUnit output
├── config/       # Project configuration
├── _internal/    # Private utilities
└── exceptions.py # Error hierarchy
```

## Data Flow

```
[Developer writes spec YAML]
        ↓
[a2aspec record] → calls agents via adapters → saves snapshots to disk
        ↓
[Snapshots committed to git]
        ↓
[a2aspec test --replay] → loads snapshots → validates against specs → reports results
        ↓
[CI passes or fails]
```

## Key Design Decisions

1. **Snapshots are files, not a database** — committed to git for versioning and review
2. **Replay is the default** — CI never calls LLMs; it replays stored outputs
3. **Adapters are pluggable** — any agent framework can be wrapped
4. **Specs are YAML** — human-readable, diffable, reviewable in PRs
5. **Semantic features are optional** — the `[semantic]` extra keeps the base install lightweight
6. **Safe eval for conditions** — pipeline routing uses AST-based evaluation, never `eval()`

## Module Dependencies

```
cli → config, spec, snapshot, diff, pipeline, reporting
pipeline → dag, executor, trace, adapters, spec, snapshot
diff → structural, semantic, engine
spec → schema, loader, validator, registry
snapshot → store, fingerprint, recorder, replay
```

## Extension Points

- **Custom adapters** — subclass `AgentAdapter`
- **Custom policies** — register validator functions with `PolicyEngine`
- **Custom reporters** — consume `ValidationResult`, `DiffResult`, `PipelineTrace`
