# design-research-problems
[![CI](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml/badge.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Coverage](.github/badges/coverage.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Examples Passing](.github/badges/examples-passing.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Public API In Examples](.github/badges/examples-api-coverage.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml)
[![Docs](https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml/badge.svg)](https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml)

`design-research-problems` is a compact library and compendium of design research
problems. It packages canonical research prompts, optimization benchmarks, and
discrete grammar-style problems behind a small, typed Python API.

## Overview

The initial release centers on three seed problem families:

- Text problems for human-subjects studies and prompt packets
- Optimization problems with typed bounds and lazy SciPy-backed solving
- Grammar problems that describe discrete design actions and optional evaluation adapters

The first catalog includes:

- `peanut_sheller_fu2010` for text-based design research
- `pill_capsule_min_area` for constrained continuous optimization
- `planar_truss_span` for a discrete topology grammar backed by `trussme`

## Quickstart

Requires Python 3.12+.
Reproducible installs are pinned to Python `3.12.12` in `.python-version`.

```bash
python3 -m venv .venv
source .venv/bin/activate
make dev
make test
PYTHONPATH=src python3 examples/catalog/list_and_load.py
```

Install the optional optimization solver support with:

```bash
pip install -e ".[opt]"
```

Install the local `TrussMe` checkout for real grammar evaluation with:

```bash
make install-trussme-local
```

## Docs

See [`docs/index.rst`](docs/index.rst) for the guide and reference layout.
Build them locally with:

```bash
make docs
```

## Contributing

Contribution guidelines live in [`CONTRIBUTING.md`](CONTRIBUTING.md).
