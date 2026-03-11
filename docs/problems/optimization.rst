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

- `battery_18650_t1_series_parallel_opt`, a tier-1 rectangular sizing benchmark
  that optimizes only series and parallel counts.
- `battery_18650_t2_layout_opt`, a tier-2 pose-aware layout benchmark that
  adds per-cell `[x_mm, y_mm, z_mm, angle_x_deg, angle_y_deg, angle_z_deg]`
  freedom while retaining constrained topology.
- `battery_18650_t3_topology_opt`, a tier-3 benchmark that introduces typed
  topology variables (cell-count and stage assignment) on top of tier-2 pose
  variables.
- `battery_18650_t4_thermal_opt`, a tier-4 benchmark that adds thermal-system
  variables on top of tier-3 topology and layout decisions using a
  PyBaMM-backed thermal model (lumped and multi-node modes).
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
