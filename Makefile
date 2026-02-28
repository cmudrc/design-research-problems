PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,$(shell if command -v python3.12 >/dev/null 2>&1; then echo python3.12; else echo python3; fi))
PIP ?= $(PYTHON) -m pip
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
MYPY ?= $(PYTHON) -m mypy
SPHINX ?= $(PYTHON) -m sphinx
UV ?= $(if $(wildcard .venv/bin/uv),.venv/bin/uv,uv)
REPRO_PYTHON ?= $(shell cat .python-version 2>/dev/null || echo 3.12.12)
REPRO_EXTRAS ?= dev opt
TRUSSME_PATH ?= /Users/work/PycharmProjects/TrussMe

.PHONY: help check-python check-uv dev install-dev repro lock \
	lint fmt fmt-check type test qa coverage \
	docstrings-check \
	examples-smoke examples-test examples-metrics \
	docs docs-build docs-check docs-linkcheck \
	install-trussme-local dev-truss test-trussme \
	ci clean

help:
	@echo "Common targets:"
	@echo "  dev                  Install project in editable mode with dev dependencies."
	@echo "  dev-truss            Install dev dependencies plus the local TrussMe checkout."
	@echo "  test                 Run the default pytest suite."
	@echo "  test-trussme         Run tests that require the real local TrussMe checkout."
	@echo "  docstrings-check     Enforce Google-style docstring policy."
	@echo "  ci                   Run the main local CI checks."

check-python:
	@$(PYTHON) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" || (echo "Python >= 3.12 is required by pyproject.toml"; exit 1)

check-uv:
	@$(UV) --version >/dev/null 2>&1 || (echo "uv is required for lock/repro targets."; exit 1)

dev:
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

install-dev: dev

repro: check-uv
	$(UV) sync --frozen --python $(REPRO_PYTHON) $(foreach extra,$(REPRO_EXTRAS),--extra $(extra))

lock: check-uv
	$(UV) lock --python $(REPRO_PYTHON)

lint: check-python
	$(RUFF) check .

fmt: check-python
	$(RUFF) format .

fmt-check: check-python
	$(RUFF) format --check .

type: check-python
	$(MYPY) src

test: check-python
	PYTHONPATH=src $(PYTEST) -m "not trussme_real" -q

qa: lint fmt-check type test

docstrings-check: check-python
	$(PYTHON) scripts/check_google_docstrings.py

coverage: check-python
	mkdir -p artifacts/coverage
	PYTHONPATH=src $(PYTEST) -m "not trussme_real" --cov=src/design_research_problems --cov-report=term --cov-report=json:artifacts/coverage/coverage.json -q
	$(PYTHON) scripts/check_coverage_thresholds.py --coverage-json artifacts/coverage/coverage.json

examples-smoke: check-python
	PYTHONPATH=src $(PYTEST) -m examples_smoke -q

examples-test: check-python
	PYTHONPATH=src $(PYTEST) -m examples_full -q

examples-metrics: check-python examples-test
	$(PYTHON) scripts/generate_examples_metrics.py
	$(PYTHON) scripts/generate_examples_badges.py

docs-build: check-python
	$(PYTHON) scripts/generate_example_docs.py
	PYTHONPATH=src $(SPHINX) -b html docs docs/_build/html -n -W --keep-going -E

docs-check: check-python
	$(PYTHON) scripts/generate_example_docs.py --check
	$(PYTHON) scripts/check_docs_consistency.py

docs-linkcheck: check-python
	PYTHONPATH=src $(SPHINX) -b linkcheck docs docs/_build/linkcheck -W --keep-going -E

docs: docs-build

install-trussme-local:
	$(PIP) install -e "$(TRUSSME_PATH)"

dev-truss: dev install-trussme-local

test-trussme: check-python
	PYTHONPATH=src $(PYTEST) -m trussme_real -q

ci: qa coverage docstrings-check docs-check examples-smoke

clean:
	rm -rf .coverage .mypy_cache .pytest_cache .ruff_cache artifacts build dist docs/_build src/design_research_problems.egg-info
	find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type f \( -name "*.pyc" -o -name ".coverage.*" \) -exec rm -f {} + 2>/dev/null || true
