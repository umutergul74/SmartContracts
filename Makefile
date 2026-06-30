.PHONY: install lint type test check smoke

install:
	uv sync --extra dev

lint:
	uv run ruff format --check .
	uv run ruff check .

type:
	uv run mypy src

test:
	uv run pytest --cov=scbounty --cov-report=term-missing

smoke:
	uv run scbounty env doctor
	uv run scbounty targets list

check: lint type test smoke

