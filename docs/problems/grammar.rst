Grammar Problems
================

Grammar problems describe discrete design actions over a library-owned state.
Generic grammar-family tooling should use the shared `GrammarProblem` contract:
`initial_state()`, `enumerate_transitions()`, `enumerate_next_states()`, and
`evaluate()`. Concrete rule methods remain problem-specific conveniences.

See :doc:`../problem_catalog/grammar` for the generated per-problem catalog pages.
For battery electronics/thermal modeling assumptions shared across grammar and
optimization tiers, see :doc:`battery_ladder`.

The catalog includes `planar_truss_span`, which translates a serializable
planar topology state into a fresh `trussme.Truss` for evaluation. It also
includes `space_truss_span`, which applies the same evaluation pattern to a
bounded 3D space-truss state. The tiered battery grammar ladder includes
`battery_18650_t1_series_parallel_grammar`,
`battery_18650_t2_layout_grammar`,
`battery_18650_t3_topology_grammar`, and
`battery_18650_t4_thermal_grammar`, which progressively unlock series-parallel
layout edits, pose-aware layout edits, explicit topology/netlist edits, and
thermal-system tuning. The catalog also includes six
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
