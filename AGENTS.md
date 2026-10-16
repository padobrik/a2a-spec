# AGENTS.md

Instructions for coding agents that work on this repository. CONTRIBUTING.md
is the short version for people; this file adds the rules that the code and
the history follow.

This file is about changing agent-handshake itself. To use agent-handshake in
another project, read `src/agent_handshake/skill/SKILL.md` instead
(`handshake skill` prints it).

## What the project is

agent-handshake is a Python CLI and library for contract tests between agents.
It records what a producer agent returns (snapshots, JSON files in git), finds
what a consumer agent reads (`handshake infer`, static analysis of Python and
TypeScript code), and checks the snapshots against the spec in CI. The checks
make no LLM calls and need no API keys.

The core must stay small and deterministic. Version 0.9 removed the semantic
rules, the pipeline command, the statistical rules, the built-in PII
validators and the LangChain adapter for this reason. Do not add them back,
and do not add features that call a model, use the network during
`handshake test`, or give different results on different runs.

## Setup

Python 3.11 or later.

```bash
pip install -e ".[dev,typescript]"
```

## Checks

Run these before every commit. They are the same steps as the `Test` job in
`.github/workflows/ci.yml`, in the same order:

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
coverage run -m pytest tests/ --tb=short
coverage report          # fails under 90 %, set in pyproject.toml
```

Other CI jobs:

```bash
# Workflow security, when you change .github/workflows/ or action.yml.
# Install the zizmor and actionlint-py versions pinned in the workflows job.
actionlint
zizmor --offline .github/workflows action.yml

# Package: build the sdist and wheel and check their metadata
pip install build twine
python -m build && twine check --strict dist/*
```

CI also checks that `import agent_handshake` works without the optional
extras, and that `src/` has no `yaml.load` (only `yaml.safe_load`).

The test suite runs in a few seconds. Run all of it, not only the file you
changed.

## Layout

```
src/agent_handshake/
├── __init__.py       public exports (__all__) and __version__
├── api.py            core API: load_snapshots and check; the CLI and plugin use it
├── cli/              Typer commands: init, record, test, diff, infer, skill
│   └── exit_codes.py 0 passed, 1 a check failed, 2 input or configuration error
├── config/           handshake.yaml: settings model and loader
├── spec/             spec schema, loader, validator, registry, removed.py
├── snapshot/         snapshot store, file format, fingerprint, recorder, replay
├── infer/            handshake infer: Python (ast) and TypeScript (tree-sitter) consumers
├── diff/             structural diff of snapshots against the git baseline
├── policy/           regex and custom policy rules
├── adapters/         FunctionAdapter, HTTPAdapter, A2AAdapter
├── reporting/        console, markdown, JUnit and GitHub annotation output
├── project.py        loads the user's adapters and scenarios
├── pytest_plugin.py  runs specs as pytest tests (entry point pytest11, name handshake)
├── exceptions.py     error hierarchy, all under HandshakeError
└── skill/SKILL.md    agent skill shipped in the wheel
tests/                unit tests, one file per module (test_<area>_<module>.py)
tests/e2e/            project scenarios run through the real handshake command
examples/             customer_support (plain code), llm_support (recorded model output)
docs/                 user documentation; docs/api.md for the core API
action.yml            the GitHub Action
scripts/              release and demo helpers
NOTES.md              design decisions and assumptions
```

## Rules for changes

- **Tests.** Every change in behaviour has a test that fails on the old code.
  A bug fix starts with the failing test.
- **End-to-end scenarios.** When a change affects what a user sees from the
  CLI, the pytest plugin or the GitHub Action, add or update a project in
  `tests/e2e/projects/`. Each project has a `scenario.yaml` with the commands,
  the expected exit codes and the text that must or must not be in the output.
  The format is in the docstring of `tests/e2e/test_projects.py`.
- **Optional dependencies.** `tree_sitter` and `tree_sitter_typescript` are
  imported inside the functions that use them, not at module level. Tests that
  need them use `pytest.importorskip`. Do the same for any new extra.
- **Removing a feature.** A spec or `handshake.yaml` that still uses it must
  fail to load with a message that names it and says what to use instead.
  Add the message to `spec/removed.py` or to `_removed_setting` in
  `config/loader.py`, with a test.
- **Snapshots.** Never edit a snapshot JSON by hand, also not in examples or
  e2e projects. Record it again with `handshake record`. If only the file
  format changes, say so in the commit body.
- **Core API first.** `handshake test` and the pytest plugin are built on
  `check` and `load_snapshots` in `api.py`. Put checking logic there, not in
  a command, so the CLI, the plugin and library users get the same result.
- **Exit codes.** Use the constants in `cli/exit_codes.py`. `1` means a check
  found a problem; `2` means the command could not run as asked (bad config,
  broken snapshot, no snapshots for a producer, missing adapter). When both
  happen, `2` wins. Do not add a third meaning.
- **Settings.** The models in `config/settings.py` forbid unknown keys, and
  the loader suggests the closest known key. A new setting goes in the model,
  in the `handshake init` template and in the docs.
- **pytest plugin.** It turns on by itself when `handshake.yaml` is in the
  rootdir. This repository has none at the root, so its own suite is not
  affected; tests of the plugin use `pytester`.
- **Errors.** A user mistake (bad YAML, broken snapshot, unknown setting) is a
  `HandshakeError` subclass with a message that names the file and the
  problem. `cli/main.py` prints it without a traceback (`--debug` shows
  one).
- **Typing.** `mypy --strict` is on for `src/`. Do not add `# type: ignore`
  without a reason in the same comment.
- **Security.** Load YAML with `yaml.safe_load`. Never `eval` or `exec` input.
  Custom validators are loaded only from the dotted path in a spec.

## Documentation

Update the documentation in the same pull request as the code:

- `CHANGELOG.md`: add an entry under `## [Unreleased]`, in the section
  `Added`, `Changed`, `Fixed` or `Removed`. Write what the user sees, not how
  the code changed.
- `NOTES.md`: add the assumption when you decide something that the request
  or the code did not decide.
- `docs/cli-reference.md` when a command, an option or an exit code changes.
- `docs/api.md` and `__all__` in `__init__.py` when the public API changes.
- `src/agent_handshake/skill/SKILL.md` when a command it uses changes.
  `tests/test_skill.py` fails when the skill names a command or an option
  that does not exist.
- `README.md` and `docs/` use short sentences and simple words, one idea per
  sentence. Keep that style.

## Commits and pull requests

- Conventional commits: `type(scope): subject`. Types: `feat`, `fix`, `docs`,
  `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Add `!` for a
  breaking change, for example `refactor!: remove the semantic engine`.
- Subject in the imperative mood, lower case after the colon, 72 characters
  or fewer. The `PR title` workflow checks the pull request title the same
  way, because it becomes the merge commit subject.
- The body says what changed for the user and why, in plain sentences.
  Reference issues with `Fixes #N`.
- Keep commits small and keep the suite green on every commit, so that each
  one can be reverted or bisected alone.
- One logical change per pull request. Fill in `.github/pull_request_template.md`.

## Releases

Only the maintainer releases (see CONTRIBUTING.md). Do not change
the version in `pyproject.toml`, `src/agent_handshake/__init__.py` or the bug
report template, and do not rename the `[Unreleased]` section, unless the
task is a release.
