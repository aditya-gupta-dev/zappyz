.PHONY: build check test

build:
	uv run --group build pyinstaller --clean --noconfirm zapisi.spec

check:
	uv run ruff check src tests
	uv run ruff format --check src tests

test:
	uv run python -m unittest discover -s tests -v
