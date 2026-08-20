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

Optional evaluator/backend setup for selected high-fidelity modes:

```bash
make install-trussme   # real planar/3D truss structural evaluation
make install-pybamm    # PyBaMM-backed battery fidelity modes
make dev-full          # install dev + all optional extras
```

## Release Publishing

Before cutting a release, run `make release-check`. The GitHub `Publish`
workflow builds and validates distributions before any upload:

- Publishing a GitHub Release tagged `v{package-version}` publishes to PyPI.
- A manual workflow run is build-only by default.
- A recovery publish requires selecting the release tag and explicitly setting
  `publish=true`; publishing from a branch is rejected.
- Every publishing path rejects a tag that differs from the version in
  `pyproject.toml`.

## Local Quality Checks

Run these before opening a pull request:

```bash
make fmt
make lint
make type
make docstrings-check
make test
make docs-check
make docs-build       # when public documentation or docstrings change
make docs-linkcheck   # when links or navigation change
make ci
```

`make ci` includes generated-document consistency but not the strict Sphinx
build or external link check, so run the conditional documentation gates shown
above when the change touches those surfaces.

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
