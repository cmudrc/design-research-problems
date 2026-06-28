# design-research-problems
[![CI](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml/badge.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Coverage](https://raw.githubusercontent.com/cmudrc/design-research-problems/HEAD/.github/badges/coverage.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Examples Passing](https://raw.githubusercontent.com/cmudrc/design-research-problems/HEAD/.github/badges/examples-passing.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/examples.yml)
[![Public API In Examples](https://raw.githubusercontent.com/cmudrc/design-research-problems/HEAD/.github/badges/examples-api-coverage.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/examples.yml)
[![Docs](https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml/badge.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml)
[![PyPI Version](https://img.shields.io/pypi/v/design-research-problems.svg)](https://pypi.org/project/design-research-problems/)
[![Python Versions](https://img.shields.io/pypi/pyversions/design-research-problems.svg)](https://pypi.org/project/design-research-problems/)

<!-- release-callout:start -->
> [!IMPORTANT]
> Current monthly release: [Jaguar Junction - May 2026](https://github.com/cmudrc/design-research-problems/milestone/3)  
> Due: June 1, 2026  
> Tracks: May 2026 work
<!-- release-callout:end -->

`design-research-problems` is a compact library and compendium of design research
problems. It packages canonical research prompts, optimization benchmarks, and
discrete grammar-style problems behind a small, typed Python API.

## Overview

- Five problem families: text, decision, optimization, grammar, and MCP, plus a linked ideation metadata catalog.
- Shared model contracts built around `Problem` and `ComputableProblem`, with family-specific subclasses on top.
- A seed catalog that includes 126 ideation prompt records plus packaged decision, optimization, grammar, and MCP benchmarks.
- A study-facing integration seam in `design_research_problems.integration` for experiment runners.
- Optional integrations for `trussme`, `pybamm`, `mcp`, Build123d, and external solver backends.
- Typed metadata, a curated public API, runnable examples, and Sphinx docs.

## Quickstart

Requires Python 3.12+.
Local workflows target Python `3.12` in `.python-version`.

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install in editable mode for local development:

```bash
make dev
make test
```

Or install from PyPI:

```bash
pip install design-research-problems
```

Optional extras:

```bash
pip install "design-research-problems[grammar]"
pip install "design-research-problems[battery]"
pip install "design-research-problems[mcp,cad]"
pip install "design-research-problems[solvers,pandas]"
pip install "design-research-problems[all]"
```

Base installs already include the SciPy-backed optimization primitives, so
there is no separate `opt` extra. Add `solvers` for external optimization
backends or `all` for the broadest packaged toolkit.

Then inspect the catalog directly from the installed package:

```bash
python3 -c "import design_research_problems as derp; print(derp.list_problems())"
```

And inspect the ideation corpus:

```bash
python3 -c "import design_research_problems as derp; print(len(derp.get_ideation_catalog().list_prompts()))"
```

Launch the packaged desktop GUIs with:

```bash
python3 -m design_research_problems.gui --app iot
python3 -m design_research_problems.gui --app truss
```

The IoT GUI renders a continuous room-temperature colorbar, and the truss GUI
only evaluates structurally when the design is not under-determined.

Run one checked-in example from repository root:

```bash
PYTHONPATH=src python examples/catalog/list_and_load.py
```

## Examples

Start with [examples/README.md](https://github.com/cmudrc/design-research-problems/blob/HEAD/examples/README.md)
for runnable examples across all problem families.

## Docs

See the [published documentation](https://cmudrc.github.io/design-research-problems/)
for quickstart, problem-family guides, generated catalog pages, and API reference.

Using VS Code? Start with the
[VS Code example guide](https://cmudrc.github.io/design-research-problems/vscode_start.html)
for a PyPI install path and source checkout example path.

Build docs locally with:

```bash
make docs
```

## Public API

The supported public surface is whatever is exported from `design_research_problems.__all__`.

Top-level exports include:

- Shared contracts and family bases: `Problem`, `ComputableProblem`, `ProblemKind`, `ProblemMetadata`, `ProblemTaxonomy`, `Citation`, `ProblemAsset`, `TextProblem`, `DecisionProblem`, `OptimizationProblem`, `GrammarProblem`, and `MCPProblem`.
- Family-specific evaluation contracts: `DecisionEvaluation`, `OptimizationEvaluation`, and `GrammarTransition`.
- Catalog access: `ProblemRegistry`, `get_problem`, `get_problem_as`, and `list_problems`.
- Study-facing integration helpers: `integration`, `resolve_problem_binding`, and `evaluate_problem_output`.
- Ideation metadata API: `IdeationCatalog`, `IdeationPromptRecord`, `IdeationPromptVariant`, `IdeationPromptFamily`, `IdeationStudy`, `EvidenceTier`, and `get_ideation_catalog`.
- Public exceptions: `MissingOptionalDependencyError` and `ProblemEvaluationError`.

## Contributing

Contribution workflow and quality gates are documented in
[CONTRIBUTING.md](https://github.com/cmudrc/design-research-problems/blob/HEAD/CONTRIBUTING.md).
