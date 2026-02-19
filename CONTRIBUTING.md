# Contributing to a2a-spec

## Development setup

```bash
git clone https://github.com/padobrik/a2a-spec.git
cd a2a-spec
pip install -e ".[dev]"
```

To install optional extras for semantic and LangChain adapters:

```bash
pip install -e ".[dev,semantic,langchain]"
```

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

## Commit style

Use the imperative mood in the subject line (`add`, `fix`, `remove`, not `added`).
Keep the subject under 72 characters. Reference issues with `Fixes #N` in the body.

## Reporting bugs

Open an issue using the **Bug report** template. Include a minimal reproducible example.

## Proposing features

Open an issue using the **Feature request** template before starting significant work,
to avoid building something that won't be merged.
