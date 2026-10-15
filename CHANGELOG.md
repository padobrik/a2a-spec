# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `a2aspec infer` generates a consumer-driven spec from the fields a consumer
  function reads and the producer's recorded snapshots.
- pytest plugin: with `--a2a` or the `a2a_config` ini option, spec files are
  collected as tests (one per snapshot); the `a2a_check` fixture validates
  live outputs.
- `a2aspec test` evaluates `embedding_similarity` semantic rules against the
  recorded input and output of each snapshot; `--no-semantic` skips them.
- `LangChainAdapter` is exported from the package root.

### Changed
- Semantic rules using `entailment` or `language_detection` now fail with
  "not implemented" instead of being silently ignored.
- Custom policy validators receive the snapshot input instead of an empty dict.
- The result header reports FAIL when any layer fails, not only structural.
- Widened upper bounds for rich, langchain-core, sentence-transformers and dev tools.

### Fixed
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

[0.1.0]: https://github.com/padobrik/a2a-spec/releases/tag/v0.1.0
