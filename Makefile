# mcp-pm Makefile — Common development tasks
#
# Copyright (c) 2025-2026 Davey Wong <wgwcko@gmail.com>
# Licensed under MIT License.

.PHONY: install dev lint typecheck test test-cov clean build publish

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

typecheck:
	mypy src/

test:
	python -m pytest tests/ -v --tb=short

test-cov:
	python -m pytest tests/ -v --tb=short --cov=src/mcp_pm --cov-report=term-missing

clean:
	rm -rf build/ dist/ *.egg-info/ .mypy_cache/ .ruff_cache/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

build: clean
	python -m build

publish: build
	python -m twine upload dist/*
