Grammar Problems
================

Grammar problems describe discrete design actions over a library-owned state.

The catalog includes `planar_truss_span`, which translates a serializable
planar topology state into a fresh `trussme.Truss` for evaluation. It also
includes `battery_pack_18650_series_parallel`, which models a complete
series-parallel battery pack with explicit cell coordinates, whole-stage and
whole-branch edits, and an optional PyBaMM-backed representative-cell
evaluation path. The catalog also includes six `planar_roof_truss_*` variants
that approximate the planar roof truss formulations discussed by Shea and
Cagan, including multi-load and symmetry-constrained cases.

Optional evaluators:

- It is not required for the base install.
- `trussme` is available as the `grammar` extra.
- `pybamm` is available as the `battery` extra.
- It is not installed in default CI.
- It is required only for real grammar evaluation.
