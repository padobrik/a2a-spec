# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `handshake init` adds `__pycache__/` to `.gitignore`. An existing file only
  gets the missing lines at the end.
- `handshake diff` rates changes by the consumers' specs: a removed or retyped
  field that a spec names is `FAIL` and says who reads it and where
  (`resolution-agent reads it at agents/resolution.py:2`); a change to a field
  no spec names is `INFO` and does not fail.
- Specs made by `handshake infer` store the read lines per field in `read_at`,
  and `reads_unknown_keys: true` when the consumer also reads keys the
  analysis cannot name (`data[key]`, input passed to another function). `diff`
  then keeps the rating of changes to fields the spec does not name, and
  `infer --check` fails if the consumer reads such keys but the spec does not
  say so.
- A core Python API: `load_snapshots(source)` and `check(spec, snapshots)`
  return a `CheckResult` with one result per snapshot (see docs/api.md).
  `handshake test` and the pytest plugin use it.
- Snapshot files carry `schema_version` (now 1). A file without it is read
  as version 1 with a warning; recording it again adds the field. A file with
  a newer version fails with a message to upgrade agent-handshake.

### Changed
- `handshake infer` fails (exit 1, no spec written) when the consumer reads a
  field the producer sent in no snapshot. Before, the field became optional,
  so inferring after a broken producer accepted the break. Pass
  `--allow-missing FIELD` for a field the producer leaves out on purpose.
- Regenerate inferred specs with `handshake infer ... --force` to add
  `read_at` and `reads_unknown_keys`. Until then `diff` cannot name the read
  lines, and `infer --check` fails for a spec whose consumer reads keys the
  analysis cannot name.
- `handshake.yaml` rejects unknown settings, also inside `storage` and `ci`,
  and names the closest known one: `Unknown setting 'spec_dir'. Did you mean
  'specs_dir'?`. Before, a typo was ignored and the default was used.
- The pytest plugin turns on by itself when it finds `handshake.yaml` in the
  directory where pytest starts or a parent up to the pytest rootdir (the
  nearest file wins), and adds the specs directory to the run (unless test
  paths are named on the command line). Turn it off with `-p no:handshake` (the plugin is now
  registered as `handshake`) or `handshake_enabled = false`.
- In the pytest plugin, a spec whose producer has no snapshots is a failed
  test instead of a skipped one.
- Exit codes are the same in every command: `0` everything passed, `1` a
  check found a problem (a broken contract, high-severity drift in `diff`,
  an out-of-date inferred spec, a failed agent call), `2` a configuration or
  input error. When both happen, the code is `2`. Before, `diff` exited 2 on
  drift and most configuration errors exited 1.
- `handshake test` treats a spec whose producer has no snapshots, a missing
  adapter in `--live`, and an empty specs directory as input errors (exit 2)
  instead of warnings or a pass. `diff` with no snapshots exits 2 instead of 0.
- `handshake test` and the pytest plugin check every snapshot file of a
  producer. Before, only the newest file of each scenario was checked.
- `handshake record` keeps a snapshot file as it is when the input, the
  output and the format version have not changed, so git shows no change.

### Fixed
- A snapshot file that is not valid JSON, is not an object, or lacks
  `agent_id`, `scenario`, `input` or `output` no longer crashes with a
  traceback. `handshake test` and `handshake diff` name the file, say what is
  wrong and exit 2; the pytest plugin fails that test with the same message.

### Removed
These were non-deterministic, unused or outside the tool's job. A spec or
`handshake.yaml` that still uses one fails to load with a message that names
it and says what to use instead.

- Semantic rules (`embedding_similarity`, and the never implemented
  `entailment` and `language_detection`), the `semantic` extra
  (sentence-transformers, numpy), `handshake test --semantic/--no-semantic`
  and the pytest option `--handshake-no-semantic`. Use a custom validator
  for checks on text.
- The `semantic` section and `ci.fail_on_semantic_drift` / `ci.drift_threshold`
  in `handshake.yaml`. Delete them.
- Similarity scoring in `handshake diff` and its `--threshold` option. A
  changed value is now a MEDIUM change, like any other structural change.
- Statistical rules (`statistical:` with `chi_squared` / `ks_test`). They
  were never checked; delete the section.
- `handshake pipeline` and the pipeline modules (`PipelineExecutor`,
  `PipelineTrace`, `PipelineExecutionError`). Test each producer-consumer
  pair with its own spec.
- The built-in validators `agent_handshake.policy.builtin.no_pii_in_output`
  and `output_not_empty`. Use a `regex` policy rule with your own patterns,
  or list the needed fields in `structural.required`.
- `LangChainAdapter` and the `langchain` extra. Call the runnable from an
  `async` function and use `FunctionAdapter`; see docs/writing-adapters.md.
- `SemanticDriftError`, which nothing raised.
- `SpecRegistry` (`agent_handshake.spec.registry`), which nothing used. Use
  `load_all_specs` and filter by `producer` or `consumer`.

## [0.8.0] - 2026-10-16

### Fixed
- A `custom` policy rule now loads its `validator` from the dotted path in
  the spec, including modules in the project directory. Before, the CLI and
  the pytest plugin never loaded it, so every `custom` rule failed with
  "not registered".
- `handshake infer` writes `inferred_from` with `/` on every OS. A spec
  inferred on Windows had `\` in it, and `handshake infer --check` could not
  find the consumer on Linux or macOS.

### Added
- The GitHub Action has an output, `test-exit-code`: the exit code of
  `handshake test`, empty when that step did not run.
- `handshake infer` and `handshake infer --check` read TypeScript and
  JavaScript consumers (`.ts`, `.mts`, `.cts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`) with the
  new `typescript` extra. They find member and subscript reads, optional
  chaining, `in` checks, destructuring and local aliases, also in nested
  objects. The code is parsed with tree-sitter; Node.js is not needed.
- `A2AAdapter(streaming=True)` uses `SendStreamingMessage`. It reads the
  server-sent events, applies status and artifact updates to the task, and
  returns the same output as without streaming. The Agent Card must declare
  `capabilities.streaming`.
- `examples/llm_support`: a triage agent that calls a hosted model with
  structured output, a plain-code consumer, snapshots recorded from the real
  model, an inferred contract and a hand-written spec with semantic and
  policy rules. CI replays it with the GitHub Action.

## [0.7.0] - 2026-10-16

### Changed
- The project is renamed from a2a-spec to agent-handshake. The A2A protocol is
  only one of the agent types it tests, and the old name read as an A2A-only
  tool. New names: package `agent-handshake`, module `agent_handshake`,
  command `handshake`, config file `handshake.yaml`, project folder
  `handshake/`, pytest options `--handshake`, `--handshake-config`,
  `--handshake-no-semantic`, ini option `handshake_config`, fixture
  `handshake_check`, and the GitHub Action `padobrik/agent-handshake`.
  `HandshakeError` and `HandshakeConfig` replace `A2ASpecError` and
  `A2ASpecConfig`. The old names are not kept: the project had no users yet.

### Added
- `A2AAdapter` reads file parts. They go under `"files"` in the output: a URL
  file keeps its `url`, a raw file is stored as `size` and `sha256`, and
  `filename` and `mediaType` are kept. Before, a reply with a file part
  raised `AdapterError`.

## [0.6.0] - 2026-10-16

### Added
- `a2aspec infer` follows nested reads: `data["customer"]["tier"]`,
  `data.get("customer", {}).get("tier")`, `"tier" in data["customer"]` and
  reads through a local name such as `customer = data["customer"]`. The
  generated spec has nested object schemas with their own `required` lists.
- `a2aspec infer --check` compares nested reads with the nested schema. A spec
  generated by an earlier version covers only the top-level object, so
  `--check` now reports the nested fields; run `a2aspec infer --force` again.
- `a2aspec record --agent ID` records only the given agents (repeatable).
- A scenario can have an `agents` list. `a2aspec record` and
  `a2aspec test --live` then call only those agents with its input. Before,
  every agent in `ADAPTERS` got every scenario.

### Changed
- `a2aspec pipeline test` checks policy and semantic rules at each step, not
  only structural rules. It has `--semantic/--no-semantic` like `a2aspec test`.
  Without the `semantic` extra, a pipeline whose specs have semantic rules now
  exits 1 with an install hint; pass `--no-semantic` to skip them.

## [0.5.0] - 2026-10-16

### Added
- A GitHub Action (`uses: padobrik/a2a-spec@v0.5.0`) that installs a2a-spec,
  runs `a2aspec infer --check` and `a2aspec test --format github`. CI runs it
  on the example project.
- Scenario `expectations` are checked: `a2aspec test` (replay and live) and the
  pytest plugin fail when an agent's output does not have the expected value.
  Before, the field in scenario files was ignored.

### Fixed
- `--format github` annotations use paths relative to the repository root, so
  they attach to the spec file when the project is in a subdirectory.
- `a2aspec pipeline test --mode live` never loaded `ADAPTERS` and failed on
  the first agent. A failed agent call now fails only its test case, steps
  without a spec show `NO SPEC` instead of `FAIL`, and unknown modes are
  rejected.

## [0.4.0] - 2026-10-16

### Added
- `a2aspec infer --check` compares every inferred spec with its consumer's
  current code and fails when the code reads a field the spec does not cover.
  Inferred specs record their consumer in the new `inferred_from` field, and
  the pytest plugin runs the same check as a `consumer_code` test.
- `a2aspec test --live` calls each spec's producer through `ADAPTERS` with
  every scenario and checks the live output without saving it. Before, the
  flag only changed the header and still replayed snapshots.

### Changed
- `a2aspec diff` rates a new field as LOW instead of HIGH, so adding a field
  no longer fails CI; a removed field stays HIGH.

### Fixed
- `a2aspec record --suite` was ignored; it now records one scenario file.
- `a2aspec test --format` was ignored. `junit` and `markdown` now print only
  the report on stdout, and the new `github` format adds a GitHub Actions
  annotation for each failure. Unknown formats are rejected.

## [0.3.2] - 2026-10-16

### Changed
- README rewritten in Simplified Technical English with a verified Get started
  guide and diagrams; it no longer documents `--format` and `--live`.

### Fixed
- The `a2aspec init` example spec: its PII regexes were double-escaped and
  matched nothing, and its semantic rule lacked `source_field`/`target_field`
  and always failed.
- `a2aspec init` writes an `ADAPTERS` template and next steps that match the
  current workflow.

## [0.3.1] - 2026-10-15

### Fixed
- `a2aspec record` never found project adapters: `a2a_spec/adapters` was
  shadowed by the library's own subpackage. Adapters now load from
  `adapters_dir` (default `./a2a_spec/adapters`) and import errors are reported.
- The customer support example records and imports correctly from its own
  directory.
- The `[record]`, `[done]` and `[diff]` labels were swallowed by rich markup.

## [0.3.0] - 2026-10-15

### Added
- `A2AAdapter` calls agents that implement the A2A protocol 1.0 through
  their Agent Card and the JSON-RPC binding; the card's version is recorded
  in snapshots.

### Changed
- `Recorder` reads adapter metadata after the call instead of before.

## [0.2.0] - 2026-10-15

### Added
- `a2aspec infer` generates a consumer-driven spec from the fields a consumer
  function reads and the producer's recorded snapshots.
- pytest plugin: with `--a2a` or the `a2a_config` ini option, spec files are
  collected as tests (one per snapshot); the `a2a_check` fixture validates
  live outputs.
- `a2aspec skill` exports a bundled agent skill for coding agents.
- `a2aspec diff --base REF` selects the git revision used as baseline.
- `a2aspec test` evaluates `embedding_similarity` semantic rules against the
  recorded input and output of each snapshot; `--no-semantic` skips them.
- `LangChainAdapter` is exported from the package root.

### Changed
- **Breaking:** `a2aspec diff` requires snapshots tracked in git; it compares
  against the version at `--base` (default `HEAD`).
- Semantic rules using `entailment` or `language_detection` now fail with
  "not implemented" instead of being silently ignored.
- Custom policy validators receive the snapshot input instead of an empty dict.
- The result header reports FAIL when any layer fails, not only structural.
- Widened upper bounds for rich, langchain-core, sentence-transformers and dev tools.

### Fixed
- `a2aspec diff` reported no differences after re-recording, because
  recording overwrites the snapshot file; it now compares against the
  committed version and reports new and deleted scenarios.
- `a2aspec diff` crashed without the `semantic` extra instead of falling back
  to token overlap.
- `LangChainAdapter` returns `{"content": ...}` for chat messages and uses
  `model_dump()` for pydantic models instead of the deprecated `.dict()`.

## [0.1.0] - 2026-02-19

### Added
- Initial public release of a2a-spec.
- `SnapshotStore` with path-traversal protection.
- `DiffEngine` for structural and semantic diff of agent outputs.
- `PipelineExecutor` for DAG-based multi-agent pipeline testing.
- CLI commands: `record`, `test`, `diff`, `pipeline`, `init`.
- Frozen dataclasses for `FieldDiff`, `SemanticComparison`, `PolicyResult`.
- Structured logging via `logging.getLogger(__name__)` in all modules.
- CI matrix across Python 3.11, 3.12, 3.13.
- Trusted Publishing workflow for PyPI releases.

[0.8.0]: https://github.com/padobrik/agent-handshake/releases/tag/v0.8.0
[0.7.0]: https://github.com/padobrik/agent-handshake/releases/tag/v0.7.0
[0.6.0]: https://github.com/padobrik/a2a-spec/releases/tag/v0.6.0
[0.5.0]: https://github.com/padobrik/a2a-spec/releases/tag/v0.5.0
[0.4.0]: https://github.com/padobrik/a2a-spec/releases/tag/v0.4.0
[0.3.2]: https://github.com/padobrik/a2a-spec/releases/tag/v0.3.2
[0.3.1]: https://github.com/padobrik/a2a-spec/releases/tag/v0.3.1
[0.3.0]: https://github.com/padobrik/a2a-spec/releases/tag/v0.3.0
[0.2.0]: https://github.com/padobrik/a2a-spec/releases/tag/v0.2.0
[0.1.0]: https://github.com/padobrik/a2a-spec/releases/tag/v0.1.0
