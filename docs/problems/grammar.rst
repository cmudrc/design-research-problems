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
`battery_18650_t1_rectangular_surrogate_grammar`,
`battery_18650_t2_pose_surrogate_grammar`,
`battery_18650_t3a_topology_surrogate_grammar`,
`battery_18650_t3b_netlist_explicit_grammar`, and
`battery_18650_t4_thermal_hybrid_grammar`. Together they expose a paired
battery ladder with clear representation/fidelity labels:

- Tier 1: rectangular pack-sizing actions scored with an analytic surrogate.
- Tier 2: pose-aware layout actions scored with analytic electrical/thermal
  surrogates.
- Tier 3A: topology-allocation actions that can be benchmarked as either an
  analytic surrogate or a projected explicit-circuit evaluation.
- Tier 3B: explicit netlist-synthesis actions scored directly by the shared
  explicit-circuit backend.
- Tier 4: thermal-topology actions with analytic, explicit-circuit, or
  hybrid-thermal scoring.

The catalog also includes six
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
- `pybamm` is available as the `battery` extra and is required for tier-4
  battery thermal evaluation.
- Core CI installs `pybamm` for battery-tier verification.
- It is required for real planar and 3D truss grammar evaluation.
