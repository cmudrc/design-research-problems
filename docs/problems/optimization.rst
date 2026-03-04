Optimization Problems
=====================

Optimization problems expose typed bounds, solver-independent constraints, and
problem-specific representative baseline `solve()` implementations.

The packaged entries include:

- `battery_pack_18650_series_parallel_cost_min`, a fixed-topology integer sizing
  problem over canonical rectangular 18650 battery packs that reuses the shared
  battery backend.
- `planar_truss_span_member_count_min`, a fixed-joint binary topology problem
  over candidate planar-truss members with a member-count objective.
- `planar_truss_span_total_length_min`, a fixed-joint binary topology problem
  over candidate planar-truss members with a total-length objective.
- `pill_capsule_min_area`, a compact nonlinear constrained problem with two
  continuous variables.
- `moneymaker_hip_pump_cost_min`, a citation-backed scalarized cost
  minimization benchmark derived from the MoneyMaker Hip Pump studies.
- `treadle_pump_ide_material_min`, a citation-backed scalarized material
  minimization benchmark derived from the IDE-style treadle pump studies.
