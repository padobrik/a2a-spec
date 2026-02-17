.PHONY: install lint format test typecheck build clean

install:
	pip install -e ".[all]"

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=a2a_spec --cov-report=term-missing

typecheck:
	mypy src/

build:
	python -m build

clean:
	rm -rf dist/ build/ *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
