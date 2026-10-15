# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- `a2aspec diff` rates a new field as LOW instead of HIGH, so adding a field
  no longer fails CI; a removed field stays HIGH.

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

[0.3.2]: https://github.com/padobrik/a2a-spec/releases/tag/v0.3.2
[0.3.1]: https://github.com/padobrik/a2a-spec/releases/tag/v0.3.1
[0.3.0]: https://github.com/padobrik/a2a-spec/releases/tag/v0.3.0
[0.2.0]: https://github.com/padobrik/a2a-spec/releases/tag/v0.2.0
[0.1.0]: https://github.com/padobrik/a2a-spec/releases/tag/v0.1.0
