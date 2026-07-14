# Contributing

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
make dev
```

If you are opening the project in VS Code, follow `docs/vscode_start.rst` for
the PyPI install path, source checkout path, interpreter selection, optional
extras, first checks, and troubleshooting.

Optional integration setup for problem families that require external backends:

```bash
make install-trussme   # truss grammar + truss optimization families
make install-pybamm    # battery grammar + battery optimization families
make dev-full          # install dev + all optional extras
```

## Local Quality Checks

Run these before opening a pull request:

```bash
make fmt
make lint
make type
make docstrings-check
make test
make docs-check
make ci
```

## Quality Gates

- `make coverage` enforces at least 95% total line coverage for the default deterministic suite.
- `make examples-test` executes the checked-in runnable examples.
- `make examples-coverage` requires every curated top-level `__all__` export to appear in at least one runnable example.

Optional but useful:

```bash
pre-commit install
pre-commit run --all-files
```

## Pull Request Guidelines

- Keep changes small enough to review quickly.
- Add or update tests for behavior changes.
- Update docs and examples when interfaces, catalogs, or workflows change.
- Describe what changed and how you validated it.

## Code Style

- Python 3.12+ target
- Ruff for linting and formatting
- Mypy for type checking
- Pytest for tests
- Google-style docstrings in `src/`, `examples/`, and `scripts/`
