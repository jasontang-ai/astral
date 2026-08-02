.PHONY: install dev check lint format typecheck typecheck-all test demo build clean

install:
	pip install -e .

dev:
	pip install -e '.[dev]'

check: lint typecheck test

lint:
	ruff check src tests
	ruff format --check src tests

format:
	ruff check --fix src tests
	ruff format src tests

typecheck:
	mypy src

# Dual type check: mypy blocking semantics locally; ty advisory second opinion.
typecheck-all: typecheck
	ty check --python .venv/bin/python src

test:
	pytest

coverage:
	pytest --cov --cov-fail-under=90

demo:
	astral demo

build:
	python -m build

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -not -path './.git/*' -exec rm -rf {} +

metrics:
	python scripts/metrics_report.py

metrics-check:
	python scripts/metrics_report.py --check
