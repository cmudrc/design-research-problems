Battery Ladder Technical Notes
==============================

This page describes the packaged battery benchmark suite as a **design-research
benchmark ladder**, not as a production battery-pack simulator. The key public
entries are:

- ``battery_18650_t1_rectangular_surrogate_*``
- ``battery_18650_t2_pose_surrogate_*``
- ``battery_18650_t3a_topology_surrogate_*``
- ``battery_18650_t3b_netlist_explicit_*``
- ``battery_18650_t4_thermal_hybrid_*``
- ``battery_fast_charge_dfn_anchor_opt``

Representation And Evaluation Modes
-----------------------------------

The battery suite now treats **representation** and **evaluation mode** as
separate concepts.

Representation modes describe what a user designs:

- ``rectangular``: classical ``S x P`` pack sizing.
- ``pose_layout``: per-cell 3D pose with fixed rectangular electrical
  semantics.
- ``topology_allocation``: pose variables plus active-cell count and stage-slot
  assignment.
- ``explicit_netlist``: explicit cells, terminals, and interconnects.
- ``thermal_topology``: topology-allocation plus thermal-system variables.
- ``fast_charge_cell``: continuous electrochemical cell-design parameters.

Evaluation modes describe how the design is scored:

- ``analytic_surrogate``: closed-form pack electrical equations and compact
  thermal proxies.
- ``explicit_circuit``: projected or native explicit-netlist scoring through
  the shared circuit backend.
- ``hybrid_thermal``: explicit-circuit electrical scoring plus the Tier-4
  thermal network.
- ``electrochemical_anchor``: direct PyBaMM DFN evaluation for the fast-charge
  anchor.

Shared Physical Scope
---------------------

The 18650 pack ladder uses one fixed cylindrical packaged cell with nominal:

- ``V_cell = 3.7 V``
- ``C_cell = 2.5 Ah``
- ``R_int = 0.05 ohm``
- ``C_rate,max = 10 C``
- ``diameter = 18 mm``
- ``length = 65 mm``

All pack benchmarks enforce hard requirements on:

- target voltage within tolerance,
- minimum capacity,
- minimum current capability,
- maximum width/depth/height,
- minimum inter-cell clearance.

Geometry from Tier 2 upward uses finite oriented cylinders. Clearance is based
on minimum **surface-to-surface** distance, not center distance. The reported
design volume is the axis-aligned bounding-box volume.

Tier Contracts
--------------

Tier 1
^^^^^^

Question:
  How well do methods handle discrete rectangular pack sizing when geometry and
  wiring are fixed?

Physically modeled:
  Canonical rectangular ``S x P`` pack relations, pack envelope, cell count,
  and a steady-state thermal proxy.

Deliberate surrogates:
  Topology is fixed to a full rectangular family, electrical behavior is
  summarized analytically, and thermal behavior is represented by a compact
  Joule-heating proxy.

Tier 2
^^^^^^

Question:
  How well do methods handle continuous geometric freedom once rectangular pack
  sizing is no longer enough?

Physically modeled:
  Per-cell 3D pose, finite-cylinder clearance, and bounding-box volume.

Deliberate surrogates:
  Electrical and thermal scoring remain analytic pack-level surrogates.

Tier 3A
^^^^^^^

Question:
  How well do methods handle asymmetric topology allocation once cell count and
  stage assignment matter?

Physically modeled:
  Active-cell count, pose, stage-slot assignment, geometric feasibility, and an
  optional projected explicit-circuit check.

Deliberate surrogates:
  The default electrical abstraction uses an imbalance surrogate instead of a
  general circuit solve. The default ``min_stage`` model is intentionally
  conservative and penalizes uneven stage populations.

Tier 3B
^^^^^^^

Question:
  How well do methods synthesize explicit pack netlists when topology is itself
  the representation?

Physically modeled:
  Explicit cells, terminals, interconnects, graph validation, and constant-load
  explicit-circuit discharge scoring.

Deliberate surrogates:
  Thermal behavior still uses a compact pack-level proxy rather than a full
  electro-thermal pack transient model.

Tier 4
^^^^^^

Question:
  How well do methods co-design topology, geometry, and thermal controls when
  temperature becomes a first-class design axis?

Physically modeled:
  Tier-3A representation plus cooling coefficient, passive cooling, ambient
  temperature, and a Tier-4 thermal network using PyBaMM-derived priors.

Deliberate surrogates:
  Candidate representation is still topology-allocation based; only the
  evaluator fidelity changes across modes.

Fast-Charge Anchor
^^^^^^^^^^^^^^^^^^

Question:
  How well do optimization methods handle a higher-fidelity electrochemical
  battery-design problem?

Physically modeled:
  A PyBaMM DFN with lumped thermal dynamics, plating, SEI growth, and CC-CV
  fast-charge evaluation.

Solver role:
  The packaged ``solve()`` method is a deterministic baseline/reference search,
  not a claim of strong optimization performance.

Shared Surrogates And Substitution Rules
----------------------------------------

Analytic pack electrical surrogates use:

.. math::

   V_{pack} \approx S \cdot V_{cell}

.. math::

   C_{pack} \approx P_{eq} \cdot C_{cell}

.. math::

   I_{limit} \approx P_{eq} \cdot C_{cell} \cdot C_{rate,max}

The effective parallel support ``P_eq`` depends on the benchmark:

- Tier 1 and Tier 2: ``P_eq = P``.
- Tier 3A and Tier 4 surrogate modes: ``P_eq`` is derived from the stage
  populations.

Two imbalance surrogates are currently supported for topology-allocation style
benchmarks:

- ``min_stage``: use the least-populated stage.
- ``harmonic_mean_stage``: use the harmonic mean of non-empty stage counts.

Projection rules are intentionally one-way in this release:

- topology-allocation candidates may be projected to a canonical explicit
  netlist for ``explicit_circuit`` scoring;
- thermal-topology candidates may be scored as analytic surrogates, projected
  explicit circuits, or hybrid thermal evaluations;
- arbitrary explicit netlists do **not** automatically reduce back to surrogate
  topology metrics unless a deterministic reduction is defined.

Backend Provenance
------------------

Battery problems accept shared backend configuration through
``[parameters.battery_backend]`` and now report evaluation provenance
explicitly. Provenance records:

- representation mode,
- evaluation mode,
- imbalance model when applicable,
- requested backend config,
- resolved backend config,
- honored vs ignored backend fields,
- cell-model source,
- thermal-prior source,
- whether a candidate was projected before scoring.

This is meant to make battery benchmark fidelity legible without pretending
that every public problem uses the same evaluator.

Validation Matrix
-----------------

The suite is validated as a benchmark family rather than via a full
battery-validation campaign:

+-------------------------------+------------------------------------------------------+
| Benchmark                     | Validation scope                                     |
+===============================+======================================================+
| Tier 1                        | analytically checked surrogate consistency           |
+-------------------------------+------------------------------------------------------+
| Tier 2                        | geometry validity and monotonicity checks            |
+-------------------------------+------------------------------------------------------+
| Tier 3A surrogate             | topology-abstraction sanity checks                   |
+-------------------------------+------------------------------------------------------+
| Tier 3B explicit              | explicit-circuit consistency checks                  |
+-------------------------------+------------------------------------------------------+
| Tier 4                        | qualitative thermal trend and mode-consistency tests |
+-------------------------------+------------------------------------------------------+
| Fast-charge DFN anchor        | PyBaMM model and solver reproducibility checks       |
+-------------------------------+------------------------------------------------------+

Background References
---------------------

- [Lithium-ion battery](https://en.wikipedia.org/wiki/Lithium-ion_battery)
- [Battery pack](https://en.wikipedia.org/wiki/Battery_pack)
- [Ohm's law](https://en.wikipedia.org/wiki/Ohm%27s_law)
- [Joule heating](https://en.wikipedia.org/wiki/Joule_heating)
- [Newton's law of cooling](https://en.wikipedia.org/wiki/Newton%27s_law_of_cooling)
- [C-rate](https://en.wikipedia.org/wiki/C-rate)
