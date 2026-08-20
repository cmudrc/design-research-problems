# design-research-problems
[![CI](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml/badge.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Coverage](https://raw.githubusercontent.com/cmudrc/design-research-problems/HEAD/.github/badges/coverage.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Examples Passing](https://raw.githubusercontent.com/cmudrc/design-research-problems/HEAD/.github/badges/examples-passing.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/examples.yml)
[![API in Examples](https://raw.githubusercontent.com/cmudrc/design-research-problems/HEAD/.github/badges/examples-api-coverage.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/examples.yml)
[![Docs](https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml/badge.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml)
[![PyPI Version](https://img.shields.io/pypi/v/design-research-problems.svg)](https://pypi.org/project/design-research-problems/)
[![Python Versions](https://img.shields.io/pypi/pyversions/design-research-problems.svg)](https://pypi.org/project/design-research-problems/)

`design-research-problems` is the benchmark-task layer in the
CMU Design Research Collective design-research ecosystem. It owns packaged
problem definitions, metadata, statements, evaluators, and task-specific assets
behind a layered, typed Python API.

## Quality Signals

- **Coverage** reports total line coverage for the default deterministic test suite; CI requires at least 95%.
- **Examples Passing** reports checked-in example scripts that execute successfully in the examples workflow.
- **API in Examples** reports curated top-level `__all__` exports referenced by runnable examples. `N/N` means every supported top-level export appears in at least one example, and CI requires 100%.

Run `make coverage`, `make examples-test`, and `make examples-coverage` to reproduce these checks locally.

## Overview

- Five problem kinds: text, decision, optimization, grammar, and MCP, plus a linked ideation metadata catalog.
- Shared model contracts built around `Problem` and `ComputableProblem`, with family-specific subclasses on top.
- A seed catalog that includes 126 ideation prompt records plus packaged decision, optimization, grammar, and MCP benchmarks.
- A study-facing integration seam in `design_research_problems.integration` for experiment runners.
- Optional integrations for `trussme`, `pybamm`, `mcp`, Build123d, and external solver backends.
- Typed metadata, a curated public API, runnable examples, and Sphinx docs.

## Quickstart

Requires Python 3.12+.
Local workflows target Python `3.12` in `.python-version`.

Start with the published base install:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install design-research-problems
```

For contributor work, clone the repository before using its Make targets:

```bash
git clone https://github.com/cmudrc/design-research-problems.git
cd design-research-problems
python -m venv .venv
source .venv/bin/activate
make dev
make test
```

Optional extras:

```bash
python -m pip install "design-research-problems[grammar]"
python -m pip install "design-research-problems[battery]"
python -m pip install "design-research-problems[mcp,cad]"
python -m pip install "design-research-problems[solvers,pandas]"
python -m pip install "design-research-problems[all]"
```

Base installs already include the SciPy-backed optimization primitives, so
there is no separate `opt` extra. Add `solvers` for external optimization
backends or `all` for the broadest packaged toolkit.

Then inspect the catalog directly from the installed package:

```bash
python -c "import design_research_problems as derp; print(derp.list_problems())"
```

And inspect the ideation corpus:

```bash
python -c "import design_research_problems as derp; print(len(derp.get_ideation_catalog().list_prompts()))"
```

Launch the packaged desktop GUIs with:

```bash
python -m design_research_problems.gui --app iot
python -m design_research_problems.gui --app truss
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
The [Guides](https://cmudrc.github.io/design-research-problems/guides.html) page
provides the shared install → quickstart → concepts/workflow → examples → API
path used across the ecosystem.

Using VS Code? Start with the
[VS Code example guide](https://cmudrc.github.io/design-research-problems/vscode_start.html)
for a PyPI install path and source checkout example path.

Check generated documentation consistency, then run the strict build:

```bash
make docs-check
make docs-build
```

## Ecosystem Role and Compatibility

This package defines tasks; it does not own participant execution, study design,
or downstream interpretation. Use the sibling layers for those responsibilities:

- [design-research-agents](https://cmudrc.github.io/design-research-agents/) owns executable participants and agent workflows.
- [design-research-experiments](https://cmudrc.github.io/design-research-experiments/) owns study design and orchestration across packages.
- [design-research-analysis](https://cmudrc.github.io/design-research-analysis/) owns validation and analysis of exported study records.

Compatibility is guaranteed for the curated top-level `__all__` surface and the
documented downstream metadata contract. `ProblemMetadata.kind` is one of
`text`, `decision`, `optimization`, `grammar`, or `mcp`. The integration seam
derives both `ProblemBinding.family` and the parallel `problem_kind` metadata
alias; Experiments copies `ProblemBinding.family` into its packet and exported
`problem_family`. Ideation prompts are a catalog subset of the `text` kind, not
a sixth problem kind.

See the umbrella
[compatibility matrix](https://cmudrc.github.io/design-research/compatibility.html)
for the component versions tested together.

## Public API

The supported public surface is whatever is exported from `design_research_problems.__all__`.

Top-level exports include:

- Shared contracts and family bases: `Problem`, `ComputableProblem`, `ProblemKind`, `ProblemMetadata`, `ProblemTaxonomy`, `Citation`, `ProblemAsset`, `TextProblem`, `DecisionProblem`, `OptimizationProblem`, `GrammarProblem`, and `MCPProblem`.
- Family-specific evaluation contracts: `DecisionEvaluation`, `OptimizationEvaluation`, and `GrammarTransition`.
- Catalog access: `ProblemRegistry`, `get_problem`, `get_problem_as`, and `list_problems`.
- Study-facing integration module: `integration`, with
  `integration.resolve_problem_binding` and
  `integration.evaluate_problem_output` as module members.
- Ideation metadata API: `IdeationCatalog`, `IdeationPromptRecord`, `IdeationPromptVariant`, `IdeationPromptFamily`, `IdeationStudy`, `EvidenceTier`, and `get_ideation_catalog`.
- Public exceptions: `MissingOptionalDependencyError` and `ProblemEvaluationError`.

## Contributing

Contribution workflow and quality gates are documented in
[CONTRIBUTING.md](https://github.com/cmudrc/design-research-problems/blob/HEAD/CONTRIBUTING.md).
