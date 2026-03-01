# design-research-problems
[![CI](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml/badge.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Coverage](https://raw.githubusercontent.com/cmudrc/design-research-problems/main/.github/badges/coverage.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Examples Passing](https://raw.githubusercontent.com/cmudrc/design-research-problems/main/.github/badges/examples-passing.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Public API In Examples](https://raw.githubusercontent.com/cmudrc/design-research-problems/main/.github/badges/examples-api-coverage.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Docs](https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml/badge.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml)

`design-research-problems` is a compact library and compendium of design research
problems. It packages canonical research prompts, optimization benchmarks, and
discrete grammar-style problems behind a small, typed Python API.

## Overview

The initial release centers on three problem families plus a linked ideation metadata catalog:

- Text problems for human-subjects studies and prompt packets
- Optimization problems with typed bounds and lazy SciPy-backed solving
- Grammar problems that describe discrete design actions and optional evaluation adapters
- An ideation catalog with prompt records, variants, families, and study summaries

The first catalog includes:

- 15 ideation-focused text prompts plus `peanut_sheller_fu2010`
- `pill_capsule_min_area` for constrained continuous optimization
- `planar_truss_span` for a discrete topology grammar backed by `trussme`

## Quickstart

Requires Python 3.12+.
Install from PyPI with:

```bash
pip install design-research-problems
```

Install the optional optimization solver support with:

```bash
pip install "design-research-problems[opt]"
```

Install the optional `trussme` grammar support with:

```bash
pip install "design-research-problems[grammar]"
```

Then inspect the catalog directly from the installed package:

```bash
python3 -c "from design_research_problems import list_problems; print(list_problems())"
```

And inspect the ideation corpus:

```bash
python3 -c "from design_research_problems import get_ideation_catalog; print(len(get_ideation_catalog().list_prompts()))"
```

For local development, reproducible installs are pinned to Python `3.12.12` in
`.python-version`:

```bash
python3 -m venv .venv
source .venv/bin/activate
make dev
make ci
```

## Docs

See the [published documentation](https://cmudrc.github.io/design-research-problems/)
for the guide and reference layout.
Build them locally with:

```bash
make docs
```

## Contributing

Contribution guidelines live in
[CONTRIBUTING.md](https://github.com/cmudrc/design-research-problems/blob/main/CONTRIBUTING.md).
