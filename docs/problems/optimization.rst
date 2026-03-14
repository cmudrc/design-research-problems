Optimization Problems
=====================

Optimization problems expose typed bounds, solver-independent constraints, and
problem-specific representative baseline `solve()` implementations.

The smooth continuous packaged benchmarks in this family continue to use SciPy
baselines.

See :doc:`../problem_catalog/optimization` for the generated per-problem catalog pages.
For deeper battery-model details and equations, see
:doc:`battery_ladder`.

The packaged entries include:

- `battery_18650_t1_rectangular_surrogate_opt`, a tier-1 rectangular sizing
  benchmark with an analytic surrogate evaluator over a fixed rectangular
  series-parallel family.
- `battery_18650_t2_pose_surrogate_opt`, a tier-2 pose-aware layout benchmark
  that adds per-cell `[x_mm, y_mm, z_mm, angle_x_deg, angle_y_deg, angle_z_deg]`
  freedom while keeping analytic electrical and thermal surrogates.
- `battery_18650_t3a_topology_surrogate_opt`, a tier-3A topology-allocation
  benchmark that adds active-cell count plus stage assignment and supports
  `analytic_surrogate` and projected `explicit_circuit` evaluation modes.
- `battery_18650_t3b_netlist_explicit_opt`, a tier-3B explicit-netlist
  benchmark that exposes open-ended transition-program design variables and
  scores candidates with the shared explicit-circuit backend.
- `battery_18650_t4_thermal_hybrid_opt`, a tier-4 thermal-topology benchmark
  that adds cooling-system variables and supports `analytic_surrogate`,
  `explicit_circuit`, and `hybrid_thermal` evaluator modes.
- `battery_fast_charge_dfn_anchor_opt`, a PyBaMM DFN-based electrochemical
  anchor benchmark whose packaged `solve()` method is a deterministic
  baseline/reference search rather than a claim of strong optimization.
- `gmpb_default_dynamic_min`, a stateful dynamic wrapper that negates the native
  Generalized Moving Peaks Benchmark maximization score to fit this package's
  minimization-oriented optimization API.
- `planar_truss_span_mass_min`, a fixed-joint binary planar-truss problem that
  minimizes structural mass under hard factor-of-safety and deflection limits.
- `planar_truss_span_deflection_min`, a fixed-joint binary planar-truss
  problem that minimizes structural deflection under hard factor-of-safety and
  mass limits.
- `planar_truss_span_fos_max`, a fixed-joint binary planar-truss problem that
  maximizes factor of safety under hard mass and deflection limits.
- `space_truss_span_mass_min`, a fixed-joint binary 3D space-truss problem
  that minimizes structural mass under hard factor-of-safety and deflection
  limits.
- `pill_capsule_min_area`, a compact nonlinear constrained problem with two
  continuous variables.
- `moneymaker_hip_pump_cost_min`, a citation-backed scalarized cost
  minimization benchmark derived from the MoneyMaker Hip Pump studies.
- `treadle_pump_ide_material_min`, a citation-backed scalarized material
  minimization benchmark derived from the IDE-style treadle pump studies.
