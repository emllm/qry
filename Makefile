# Project Makefile for emllm (Large Language Model Email Message Language)

# Project name
PROJECT_NAME = emllm

# Poetry environment
POETRY := poetry

# Python paths
PYTHON := $(shell $(POETRY) env info --path)/bin/python
PYTHON_SRC := src/$(PROJECT_NAME)

.PHONY: install test lint clean build publish docs start-server test-message test-api test-cli

# Install dependencies and package
install:
	$(POETRY) install

# Run all tests
.PHONY: test
test:
	$(PYTHON) -m pytest tests/ --cov=$(PYTHON_SRC) --cov-report=term-missing

# Run API tests
.PHONY: test-api
test-api:
	$(PYTHON) -m pytest tests/test_api.py

# Run CLI tests
.PHONY: test-cli
test-cli:
	$(PYTHON) -m pytest tests/test_cli.py

# Run validator tests
.PHONY: test-validator
test-validator:
	$(PYTHON) -m pytest tests/test_validator.py

# Run linters
.PHONY: lint
lint:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .
	$(PYTHON) -m flake8 .

# Run type checking
.PHONY: type-check
type-check:
	$(PYTHON) -m mypy .

# Clean up
.PHONY: clean
clean:
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage
	rm -rf htmlcov/

# Build package
.PHONY: build
build:
	$(POETRY) version patch
	$(POETRY) build

# Publish package to PyPI
.PHONY: publish
publish: build
	$(POETRY) publish --no-interaction

# Generate documentation
.PHONY: docs
docs:
	$(PYTHON) -m pdoc --html --output-dir docs .

# Clean up
.PHONY: clean
clean:
	$(POETRY) env remove
	rm -rf .mypy_cache/ .pytest_cache/ .coverage/ .coverage.* coverage.xml htmlcov/ .cache/ .tox/ .venv/ .eggs/ *.egg-info/ dist/ build/ docs/

# Start REST server
.PHONY: start-server
start-server:
	$(PYTHON) -m emllm.cli rest --host 0.0.0.0 --port 8000

# Test message parsing
.PHONY: test-message
test-message:
	$(PYTHON) -m emllm.cli parse "From: test@example.com\nTo: recipient@example.com\nSubject: Test\n\nHello World"

# Run full test suite
.PHONY: test-all
test-all: lint type-check test
	echo "All tests passed!"
