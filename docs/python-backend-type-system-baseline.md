# Python Backend Type-System Baseline

`ty` is the only required type checker for the Python backend.

## Required Scope

Required type checking now covers all `python/**` sources.

`tests/**` remain outside required type checking for now. They still run under Ruff and pytest, but they are an intentional deferral from the enforced `ty` contract.

## Required Verification

The active local verification commands are:

- `uv run --group dev ruff check python tests`
- `uv run --group dev pytest -q`
- `uv run --group dev ty check python --error-on-warning`

## Contract Notes

- `pyproject.toml` defines `ty` via `tool.ty.environment` with Python 3.13 and the `python` source root.
- CI runs Ruff, pytest, and the widened `ty` check as required quality gates.
