Grammar Problems
================

Grammar problems describe discrete design actions over a library-owned state.
Generic grammar-family tooling should use the shared `GrammarProblem` contract:
`initial_state()`, `enumerate_transitions()`, `enumerate_next_states()`, and
`evaluate()`. Concrete rule methods remain problem-specific conveniences.

See :doc:`../problem_catalog/grammar` for the generated per-problem catalog pages.

The catalog includes `planar_truss_span`, which translates a serializable
planar topology state into a fresh `trussme.Truss` for evaluation. It also
includes `space_truss_span`, which applies the same evaluation pattern to a
bounded 3D space-truss state. It also
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
The catalog also includes `iot_home_cooling_system_design`, which uses a
typed state of IoT products and links over a fixed house geometry and reports
`total_cost`, `peak_temp_c`, `capital_cost`, and `operation_cost` from a
deterministic MATLAB-parity thermal and cost simulation.
The catalog also includes `truss_analysis_program_design`, a direct port of
the MATLAB Truss Analysis Program mechanics with discrete joint/member/load
edits and deterministic `mass_kg` plus `min_fos` structural evaluation.

Optional evaluators:

- It is not required for the base install.
- `trussme` is available as the `grammar` extra.
- `pybamm` is available as the `battery` extra.
- It is not installed in default CI.
- It is required for real planar and 3D truss grammar evaluation.
