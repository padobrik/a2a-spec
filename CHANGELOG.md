# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
