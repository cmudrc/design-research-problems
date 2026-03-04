Optimization Problems
=====================

Optimization problems expose typed bounds, solver-independent constraints, and
problem-specific representative baseline `solve()` implementations.

The smooth continuous packaged benchmarks in this family continue to use SciPy
baselines. If you install ``design-research-problems[solvers]``, the
open-ended battery co-design optimizer will automatically prefer a ``pymoo``
genetic search, then a ``nevergrad`` derivative-free search, and otherwise
fall back to the built-in deterministic local search.

See :doc:`../problem_catalog/optimization` for the generated per-problem catalog pages.

The packaged entries include:

- `battery_pack_18650_open_ended_capacity_max`, an explicit 18650 transition-program
  co-design problem that maximizes delivered capacity under the shared battery
  backend.
- `gmpb_default_dynamic_min`, a stateful dynamic wrapper that negates the native
  Generalized Moving Peaks Benchmark maximization score to fit this package's
  minimization-oriented optimization API.
- `battery_pack_18650_series_parallel_cost_min`, a fixed-topology integer sizing
  problem over canonical rectangular 18650 battery packs that reuses the shared
  battery backend.
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
