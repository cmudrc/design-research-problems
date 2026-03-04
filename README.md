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

The initial release centers on four problem families plus a linked ideation metadata catalog:

- Text problems for human-subjects studies and prompt packets
- Decision problems with typed discrete or empirical evaluation interfaces
- Optimization problems with typed bounds and representative built-in baselines
- Grammar problems that describe discrete design actions and optional evaluation adapters
- An ideation catalog with prompt records, variants, families, and study summaries

The public problem model now centers on a shared ``Problem`` documentation base
and a ``ComputableProblem`` evaluation layer, with family-specific subclasses on
top. Problem-family interchangeability is defined by those family base classes,
not by matching catalog capability flags across different kinds.

The first catalog includes:

- 40 ideation-focused text prompts
- `battery_pack_18650_open_ended_capacity_max` for explicit 18650 layout-and-wiring capacity maximization under the shared battery backend
- `gmpb_default_dynamic_min` for a stateful dynamic minimization wrapper around the Generalized Moving Peaks Benchmark
- `pill_capsule_min_area` for constrained continuous optimization
- `battery_pack_18650_series_parallel_cost_min` for fixed-topology rectangular 18650 pack sizing under the shared battery backend
- `planar_truss_span_mass_min`, `planar_truss_span_deflection_min`, and `planar_truss_span_fos_max` for fixed-joint planar truss structural optimization under real `trussme` evaluation
- `space_truss_span_mass_min` for fixed-joint 3D space-truss structural optimization under the same shared truss backend
- `planar_truss_span` for the original seed planar truss grammar backed by `trussme`
- `space_truss_span` for a bounded 3D space-truss grammar backed by `trussme`
- `battery_pack_18650_open_ended` for explicit 18650 cell-by-cell graph-netlist co-design backed by an optional PyBaMM-shaped single-cell surrogate plus a library-owned pack solver
- `battery_pack_18650_series_parallel` for explicit 18650 series-parallel pack co-design backed by the same optional PyBaMM-shaped single-cell surrogate plus a library-owned pack solver
- six `planar_roof_truss_*` variants that approximate the roof-truss formulations reported by Shea and Cagan
- `moneymaker_hip_pump_cost_min` for a citation-backed scalarized pump benchmark
- `treadle_pump_ide_material_min` for a citation-backed scalarized treadle-pump benchmark

## Quickstart

Requires Python 3.12+.
Install from PyPI with:

```bash
pip install design-research-problems
```

Install the optional `trussme` truss support with:

```bash
pip install "design-research-problems[grammar]"
```

The representative optimization baselines are included in the base install.

Install the optional external optimization backends with:

```bash
pip install "design-research-problems[solvers]"
```

The smooth continuous benchmarks continue to use SciPy baselines, while the
open-ended battery co-design optimizer will automatically prefer `pymoo`, then
`nevergrad`, and finally fall back to the built-in deterministic local search.
The GMPB wrapper instead uses a simple random-search baseline because each
evaluation advances a dynamic benchmark state.

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
