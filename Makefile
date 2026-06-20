.PHONY: test lint build check

test:
	python -m pytest

lint:
	python -m ruff check .

build:
	python -m build

check:
	python -m compileall src tests
	python -m pytest
	python -m ruff check .
	python -m build
