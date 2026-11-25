VENV ?= .venv
PY := $(VENV)/bin/python

.PHONY: install check lint typecheck test build update-openapi

install:
	uv venv -p 3.9 $(VENV) || python3 -m venv $(VENV)
	uv pip install -p $(VENV) -e ".[dev]" || $(PY) -m pip install -e ".[dev]"

lint:
	$(VENV)/bin/ruff check src tests examples
	$(VENV)/bin/ruff format --check src tests examples

typecheck:
	$(VENV)/bin/mypy

test:
	$(VENV)/bin/pytest -q

check: lint typecheck test

build:
	rm -rf dist && uv build

update-openapi:
	curl -fsS https://api.webcite.co/api/v1/openapi.json -o tests/fixtures/openapi.json
