

.PHONY: help install update-deps uv-sync activate build check test test-smoke clean clean-full lint autocorrect format inspector

help:
	@echo "Dependency Management:"
	@echo "  setup         - Set up the environment"
	@echo "  install       - Install dependencies using poetry"
	@echo "  update-deps   - Update dependencies"
	@echo "  uv-sync       - Create uv lockfile"

	@echo "Build and Check:"
	@echo "  build         - Build the project"
	@echo "  check         - Run linting and tests"

	@echo "Testing:"
	@echo "  test          - Run unit tests"
	@echo "  test-smoke    - Run smoke tests"

	@echo "Cleaning:"
	@echo "  clean-full    - Clean up all including virtual environment"
	@echo "  - clean       - Clean up cache and temporary files"

	@echo "Linting:"
	@echo "  lint                - Run format and autocorrect"
	@echo "  - lint-autocorrect  - Run ruff check --fix"
	@echo "  - lint-format       - Run ruff format"

	@echo "Helpers:"
	@echo "  inspector     - Run MCP Inspector"

install:
	poetry install
	poetry install -E dev

uv-sync:
	@echo "Running uv sync..."
	run uv sync

check: lint test test-smoke

test:
	@echo "Running pytest..."
	poetry run pytest

inspector:
	@echo "Running MCP Inspector..."
	npx @modelcontextprotocol/inspector

test-smoke:
	poetry run es_knowledge_base_mcp --help

lint: autocorrect format

autocorrect:
	@echo "Running ruff check --fix..."
	poetry run ruff check . --fix

format:
	@echo "Running ruff format..."
	poetry run ruff format .

clean:
	@echo "Cleaning up..."
	rm -rf __pycache__ **/__pycache__
	rm -rf .pytest_cache **/.pytest_cache
	rm -rf .ruff_cache **/.ruff_cache
	rm -rf **/.pyc
	rm -rf **/.pyo

clean-full: clean
	@echo "Cleaning up all..."
	rm -rf .venv

setup:
	@echo "Setting up environment..."
	python3 -m venv .venv
	./.venv/bin/python3 -m pip install poetry
	./.venv/bin/poetry install
	echo "Activate the environment with 'source .venv/bin/activate'"

update-deps:
	@echo "Updating dependencies..."
	./.venv/bin/poetry update