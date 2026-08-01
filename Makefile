# Makefile for docker-reg-tool

.PHONY: install test lint clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

lint:
	ruff check src/
	ruff format --check src/

format:
	ruff format src/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf build/ dist/ *.egg-info .pytest_cache htmlcov/

build: clean
	python -m build

publish: build
	twine upload dist/*
