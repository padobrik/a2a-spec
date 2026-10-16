# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this project is

agent-handshake: contract tests for agent handoffs. It records what one agent
returns, statically infers what the next agent reads from it, and checks the
two against each other in CI with no LLM calls and no API keys. Python 3.11+,
a Typer CLI named `handshake`, a pytest plugin and a GitHub Action
(`action.yml`).

The public API is `src/agent_handshake/__init__.py`. User-visible behaviour is
documented in `README.md` and `docs/` — those are authoritative; update them
when behaviour changes.

## Commands

```bash
make install      # pip install -e ".[all]" (includes dev and typescript extras)
make lint         # ruff check src/ tests/
make format       # ruff format src/ tests/
make test         # pytest tests/ -v --tb=short
make typecheck    # mypy src/        (strict; src only, tests are not typed)
make build        # python -m build

# all checks at once (what CI runs):
ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ && pytest tests/
```

Run a single test file or test with `pytest tests/test_spec_loader.py` and
`pytest tests/test_spec_loader.py -k name`. Run only the end-to-end scenarios
with `pytest tests/e2e/`.

Coverage must stay above 90% (`fail_under = 90` in the coverage report).

## Repository map

```
src/agent_handshake/
├── cli/          # Typer commands: init, record, test, diff, infer, skill
├── spec/         # Spec schema, loading, validation, registry, removed-rule errors
├── snapshot/     # Record, replay, store, fingerprint, baseline (git)
├── diff/         # Structural comparison with severities
├── infer/        # Static readers: Python AST and tree-sitter TS consumers
├── adapters/     # Agent wrappers: function, HTTP, A2A
├── policy/       # Policy engine (user regex rules, custom validators)
├── reporting/    # Console, Markdown, JUnit, GitHub output
├── config/       # handshake.yaml loading and settings
├── pytest_plugin.py   # inert unless enabled (--handshake or ini option)
└── skill/SKILL.md     # agent skill shipped inside the package
tests/            # unit tests, one file per module
tests/e2e/        # real-CLI scenarios (see below)
examples/         # runnable examples; the only place vendor names may appear
docs/             # authoritative user documentation
NOTES.md          # recorded assumptions for ambiguous decisions
```

## Testing rules

- New or changed behaviour needs tests in `tests/`, mirroring the module
  layout (`tests/test_<module>.py`).
- Anything that changes what a user sees from the CLI, the pytest plugin or
  the GitHub Action also needs an end-to-end scenario: a directory under
  `tests/e2e/projects/` with a `scenario.yaml` listing commands, expected
  exit codes and required output substrings (see
  `tests/e2e/test_projects.py`). CI runs scenarios against the dev install
  and against the built wheel.
- The pytest plugin must stay inert unless enabled, so tests for unrelated
  suites do not pick it up.

## Conventions

- Style is enforced, not negotiated: ruff (line length 100, rules in
  `pyproject.toml`), mypy strict on `src/`, pre-commit hooks.
- Commits: imperative mood, conventional form `type(scope): subject`, subject
  under 72 characters (`docs:`, `fix(cli):`, `refactor!:`, ...). PR titles
  are validated by a workflow against the same pattern — a non-conforming
  title fails CI.
- Keep commit messages and PR descriptions free of AI vendor and assistant
  names.
- Use `yaml.safe_load`, never `yaml.load` — a CI step greps for it and fails.
- Docs and the README use deliberately plain English: short sentences, no
  idioms, no marketing words. Do not "improve" this style.
- Breaking changes use `!` in the commit type and are noted in
  `CHANGELOG.md`.

## Removed features — do not reintroduce

The 0.9 cycle removed non-deterministic or unused features. If you find
yourself reaching for one of these, check `NOTES.md` and `CHANGELOG.md`
first: semantic rules and the `semantic` extra, similarity scoring in
`diff`, statistical rules, the pipeline command, the built-in PII and
non-empty validators, the LangChain adapter, `safe_eval`.
A spec or `handshake.yaml` that still uses a removed feature must fail to
load with a message naming it (`spec/removed.py`, `config/loader.py`);
silently ignoring old keys would turn old checks into false passes.

## Version bumps

A release bumps the version in three places — `pyproject.toml`,
`src/agent_handshake/__init__.py` and the bug report template — and renames
`## [Unreleased]` in `CHANGELOG.md`. CI fails when a version has no matching
CHANGELOG section. See "Releasing" in `CONTRIBUTING.md`.

## Before opening a pull request

1. All checks pass locally (command above), including `pytest tests/e2e/`.
2. One logical change per PR.
3. Docs, tests and CHANGELOG updated with the change, not after it.
