Grammar Problems
================

Grammar problems describe discrete design actions over a library-owned state.

The catalog includes `planar_truss_span`, which translates a serializable
planar topology state into a fresh `trussme.Truss` for evaluation. It also
includes `battery_pack_18650_series_parallel`, which models a complete
rectangular series-parallel battery pack with explicit cell coordinates,
whole-stage and whole-branch edits, and an optional evaluation path that uses
PyBaMM to extract a fixed-ambient single-cell surrogate while the package owns
the pack-level circuit solve. A supported PyBaMM installation is required for
that battery evaluation path. The catalog also includes
`battery_pack_18650_open_ended`, which starts from a single 18650 cell and
exposes explicit interconnect edits over a full battery graph netlist under
that same shared backend. The catalog also includes six
`planar_roof_truss_*` variants that approximate the planar roof truss
formulations discussed by Shea and Cagan, including multi-load and
symmetry-constrained cases.

Optional evaluators:

- It is not required for the base install.
- `trussme` is available as the `grammar` extra.
- `pybamm` is available as the `battery` extra.
- It is not installed in default CI.
- It is required only for real grammar evaluation.
