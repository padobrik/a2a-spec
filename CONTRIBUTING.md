# Contributing to agent-handshake

## Development setup

```bash
git clone https://github.com/padobrik/agent-handshake.git
cd agent-handshake
pip install -e ".[dev]"
```

To install the optional extra for TypeScript consumers:

```bash
pip install -e ".[dev,typescript]"
```

### With Nix

`flake.nix` has two development shells:

```bash
nix develop        # tools from nixpkgs, the checkout installed in editable mode
nix develop .#uv   # a .venv with the dev and typescript extras from PyPI, as in CI
```

The default shell needs no network after the first build. a2a-sdk 1.x is not
in nixpkgs, so `tests/test_a2a_interop.py` is skipped there; use the `uv`
shell to run it. ruff and mypy come from nixpkgs and can be newer or older
than the versions CI installs.

`nix build` and `nix flake check` build the `handshake` command with
nixpkgs' default Python and run the test suite.
`nix run github:padobrik/agent-handshake -- --version` runs it without
installing.

## Running the checks

```bash
# Tests
pytest tests/

# Lint + format
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/

# All at once
ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ && pytest tests/
```

Pre-commit hooks (optional but recommended):

```bash
pre-commit install
```

## Pull request process

1. Fork the repo and create a branch from `main`.
2. Make your changes with tests covering new behaviour.
3. Ensure all checks pass locally before pushing.
4. Open a PR — the CI matrix (Python 3.11 / 3.12 / 3.13) must be green before merge.
5. Keep PRs focused: one logical change per PR.

## End-to-end scenarios

`tests/e2e/projects/` holds small projects that run through the real `handshake` command:
one directory per scenario, with a `scenario.yaml` listing the commands, the expected exit
codes and the text the output or files must contain (see `tests/e2e/test_projects.py`).
CI runs them with the development install and again against the built wheel. Add a
scenario when a change affects what a user sees from the CLI, the pytest plugin or the
GitHub Action.

## Commit style

Use the imperative mood in the subject line (`add`, `fix`, `remove`, not `added`).
Keep the subject under 72 characters. Reference issues with `Fixes #N` in the body.

## Reporting bugs

Open an issue using the **Bug report** template. Include a minimal reproducible example.

## Proposing features

Open an issue using the **Feature request** template before starting significant work,
to avoid building something that won't be merged.

## Releasing

1. In a pull request, bump the version in `pyproject.toml`, `src/agent_handshake/__init__.py`
   and the bug report template, and rename `## [Unreleased]` in `CHANGELOG.md` to
   `## [X.Y.Z] - YYYY-MM-DD`. CI fails if the version has no CHANGELOG section.
2. After the pull request is merged, tag the merge commit on `main` and push the tag:

   ```bash
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```

The `Release` workflow checks that the tag matches the version and that the CHANGELOG
section exists, runs CI, publishes to PyPI, creates the GitHub release with the
CHANGELOG section as its notes, and installs the new version from PyPI to check it.
