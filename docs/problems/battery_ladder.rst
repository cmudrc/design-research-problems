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

Pack Compatibility Matrix
^^^^^^^^^^^^^^^^^^^^^^^^^

For the pack ladder, the public matrix is intentionally sparse but ordered.
Each cell is written as ``electrical path / thermal path``. The legend is:

- ``native``: the evaluator works directly on the representation.
- ``projected``: the representation is deterministically projected before that
  evaluator component runs.
- ``promoted``: missing detail is filled in by documented deterministic
  defaults.
- ``unsupported``: the pairing is intentionally rejected.

.. list-table::
   :header-rows: 1

   * - Representation
     - ``analytic_surrogate``
     - ``explicit_circuit``
     - ``hybrid_thermal``
   * - ``rectangular``
     - ``native / native``
     - ``promoted / native``
     - ``promoted / promoted``
   * - ``pose_layout``
     - ``native / native``
     - ``promoted / native``
     - ``promoted / promoted``
   * - ``topology_allocation``
     - ``native / native``
     - ``projected / native``
     - ``projected / promoted``
   * - ``explicit_netlist``
     - ``unsupported``
     - ``native / native``
     - ``native / promoted``
   * - ``thermal_topology``
     - ``native / native``
     - ``projected / native``
     - ``projected / native``

The only intentional public pack-matrix gap is
``explicit_netlist + analytic_surrogate``. The package rejects that pairing
instead of silently reducing a general netlist to a surrogate topology model.

Two row-specific notes matter:

- ``thermal_topology + analytic_surrogate`` is supported, but analytic scoring
  ignores candidate-specific thermal-control variables by contract.
- ``thermal_topology + hybrid_thermal`` stays ``projected / native`` because
  the candidate already contains native thermal-network variables; only the
  electrical side is projected to the shared explicit-circuit backend.

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

Adaptation rules are intentionally one-way in this release:

- topology-allocation candidates may be projected to a canonical explicit
  netlist for ``explicit_circuit`` scoring;
- lower-detail rectangular and pose-layout candidates may be promoted to a
  canonical series-parallel circuit for explicit scoring;
- hybrid thermal scoring may promote lower-detail pack representations to one
  deterministic thermal context rather than inventing representation-specific
  heuristics at runtime;
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
- electrical path (`native`, `projected`, or `promoted`),
- thermal path (`native`, `promoted`, or `none`),
- cell-model source,
- thermal-prior source,
- promoted-only assumed defaults when applicable,
- adaptation notes that explain any projections or promotions.

This is meant to make battery benchmark fidelity legible without pretending
that every public problem uses the same evaluator.

Electrical Backend Modes
------------------------

For explicit-circuit and hybrid-thermal evaluation, the shared backend now
distinguishes between a compact default ECM path and a medium-fidelity pulse
path:

- ``auto -> pybamm_ecm`` keeps the existing one-RC Thevenin-style surrogate as
  the default for backwards compatibility and fast screening.
- ``pybamm_ecm_2rc`` adds a second relaxation branch and is fit from live
  single-cell PyBaMM SPM traces over a compact SOC/temperature pulse-rest
  design.
- ``pybamm_direct`` runs a direct PyBaMM SPM discharge for **ideal
  series-parallel** packs when a higher-cost reference evaluation is worth the
  runtime.

The intended claim for ``pybamm_ecm_2rc`` is deliberately narrow:

  scientifically grounded for conceptual pack ranking and first-order transient
  voltage prediction under benchmarked discharge and pulse/rest conditions,
  with explicit limits outside those regimes.

The backend still does **not** claim to cover:

- strong-hysteresis chemistries unless a later hysteresis mode is added;
- aggressive charge or regenerative operating histories;
- arbitrary asymmetric explicit-netlist current-split problems through the
  ``pybamm_direct`` path;
- production BMS use, safety-critical prediction, or plating-risk claims.

Backend-Config Example Variants
-------------------------------

Three packaged catalog variants now pin one non-default backend configuration
directly in their manifests:

- ``battery_18650_t3a_topology_explicit_2rc_opt``: projected explicit-circuit
  scoring on the topology-allocation rung.
- ``battery_18650_t3b_netlist_explicit_2rc_grammar``: native explicit-netlist
  grammar evaluation with the same backend choice.
- ``battery_18650_t4_thermal_hybrid_2rc_opt``: hybrid thermal scoring with the
  same electrical backend selection.

All three variants use the same manifest payload:

.. code-block:: toml

   [parameters.battery_backend]
   cell_model_mode = "pybamm_ecm_2rc"
   thermal_mode = "isothermal"

   [parameters.battery_backend.parameterization]
   parameter_set = "Marquis2019"

The intent is to surface a concrete medium-fidelity backend choice in the
public catalog without changing the underlying representation contracts of the
base tiers.

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

For the shared explicit battery backend, validation is split into two layers:

- always-on invariant checks for KCL/KVL consistency, SOC/state boundedness,
  discharge monotonicity, long-rest OCV convergence, and energy/loss sanity;
- marked ``pybamm_real`` oracle checks against live PyBaMM single-cell
  pulse/rest and short dynamic traces, plus small symmetric/asymmetric pack
  sentinels using the fitted backend models.

Background References
---------------------

- [Lithium-ion battery](https://en.wikipedia.org/wiki/Lithium-ion_battery)
- [Battery pack](https://en.wikipedia.org/wiki/Battery_pack)
- [Ohm's law](https://en.wikipedia.org/wiki/Ohm%27s_law)
- [Joule heating](https://en.wikipedia.org/wiki/Joule_heating)
- [Newton's law of cooling](https://en.wikipedia.org/wiki/Newton%27s_law_of_cooling)
- [C-rate](https://en.wikipedia.org/wiki/C-rate)
