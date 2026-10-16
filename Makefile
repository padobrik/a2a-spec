.PHONY: install lint format test typecheck build clean benchmark

install:
	pip install -e ".[all]"

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

test:
	pytest tests/ -v --tb=short

test-cov:
	coverage run -m pytest tests/ -v
	coverage report

typecheck:
	mypy src/

benchmark:
	python scripts/benchmark.py

build:
	python -m build

clean:
	rm -rf dist/ build/ *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
