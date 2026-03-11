Battery Ladder Technical Notes
==============================

This page explains the shared electronics, geometry, and thermal abstractions
used by the tiered 18650 battery problems:

- ``battery_18650_t1_series_parallel_*``
- ``battery_18650_t2_layout_*``
- ``battery_18650_t3_topology_*``
- ``battery_18650_t4_thermal_*``

Model Scope
-----------

The battery ladder uses one fixed cylindrical 18650 cell model with these
nominal properties:

- ``V_cell = 3.7 V``
- ``C_cell = 2.5 Ah``
- ``R_int = 0.05 ohm``
- ``C-rate_max = 10 C``
- ``diameter = 18 mm``
- ``length = 65 mm``

All tiers enforce hard constraints on:

- pack voltage matching within tolerance,
- minimum capacity,
- minimum current capability,
- geometric envelope dimensions,
- minimum inter-cell clearance.

Electrical Approximation
------------------------

For a classical series-parallel pack abstraction:

.. math::

   V_{pack} \approx S \cdot V_{cell}

.. math::

   C_{pack} \approx P_{eq} \cdot C_{cell}

.. math::

   I_{limit} \approx P_{eq} \cdot C_{cell} \cdot C_{rate,max}

``P_eq`` is the effective parallel population:

- Tier 1 and Tier 2: ``P_eq = P`` (explicit rectangular ``S x P``).
- Tier 3 and Tier 4: ``P_eq`` is limited by the least-populated series stage,
  i.e., the bottleneck stage in the explicit topology assignment.

This stage-bottleneck behavior intentionally makes topology decisions matter:
one weak stage reduces total deliverable capacity/current.

Connection Count
----------------

Connection metrics are reported for all tiers as a shared complexity/cost proxy.
Two common formulas are used in the ladder:

- Tier 1/2 rectangular wiring proxy:

.. math::

   N_{conn,t1} = (S + 1)\max(P - 1, 0)

- Tier 3/4 stage-assignment topology proxy:

.. math::

   N_{conn,t3} = \sum_{i=1}^{S}\max(n_i - 1, 0) + \max(S - 1, 0)

where :math:`n_i` is the number of cells assigned to stage :math:`i`.

Geometry and Spacing
--------------------

Tier 2 and above expose per-cell 3D pose variables:

.. math::

   \left[x_{mm}, y_{mm}, z_{mm}, \alpha_x, \alpha_y, \alpha_z\right]

Each cell is represented as an oriented finite cylinder. Feasibility uses
minimum **surface** clearance (not center distance), based on pairwise segment
distance between cylinder axes and then subtracting cell diameter.

Pack envelope metrics come from the axis-aligned bounding box:

.. math::

   V_{design} = W \cdot D \cdot H

The envelope limits in the benchmark are hard constraints, not soft penalties.

Thermal Proxy
-------------

Tier-1 through Tier-3 use a compact steady-state Joule-heating proxy.
Tier-4 upgrades this to a **PyBaMM-backed** thermal model by extracting
Thevenin thermal priors (resistance-vs-SOC and thermal conductance parameters)
and solving either a lumped or multi-node network.

Shared heating relation:

.. math::

   I_{cell} = \frac{I_{load}}{P_{eq}}

.. math::

   q_i = I_{cell}^2 \cdot R_{eff}(SOC_{ref})

Lumped ablation mode:

.. math::

   T_{max} = T_{amb} + \frac{N_{cell}q_i}{G_{eff}}

Tier-4 default multi-node mode (steady-state):

.. math::

   G_{cs}(T_{core,i} - T_{surf,i}) = q_i

.. math::

   G_{cs}(T_{surf,i} - T_{core,i})
   + \sum_j G_{ij}(T_{surf,i} - T_{surf,j})
   + G_{sc,i}(T_{surf,i} - T_{cool}) = 0

.. math::

   \sum_i G_{sc,i}(T_{cool} - T_{surf,i})
   + G_{cool,amb}(T_{cool} - T_{amb}) = 0

where:

- :math:`G_{ij}` uses a geometry-derived neighbor graph (clearance threshold +
  exponential distance decay).
- :math:`G_{sc,i}` includes both PyBaMM prior conductance and
  :math:`hA_{cell}` with airflow shadowing.
- reported ``max_temperature_c`` is :math:`\max_i(T_{core,i})` for a
  conservative hotspot metric.

Tier-4 unlocks ``h`` (convective coefficient), ``G_passive``, ambient
temperature, and network-model parameters via manifest knobs. Lower tiers keep
thermal settings fixed.

PyBattMo/BattMo is intentionally **not** part of the runtime path in this
release to avoid mandatory Julia/JIT coupling in baseline CI and packaged
benchmarks.

Objective Scalarization
-----------------------

All optimization tiers minimize the same normalized scalarized objective:

.. math::

   J = w_V \hat{V} + w_C \hat{N}_{cell} + w_T \hat{T} + \lambda \, \phi(x)

with:

- ``hat(V)`` as normalized design volume,
- ``hat(N_cell)`` as normalized cell-count/cost proxy,
- ``hat(T)`` as normalized peak-temperature rise,
- ``phi(x)`` as total hard-constraint violation penalty.

Weights are configured per tier from manifest parameters
(``objective_weights.*``), not hardcoded in benchmark logic.

Why The Ladder Matters
----------------------

The tiered progression is designed to expose increasing design freedom while
keeping a stable reporting contract:

- Tier 1: topology sizing only (``S,P``).
- Tier 2: Tier 1 topology + full pose freedom.
- Tier 3: Tier 2 geometry + explicit topology/cell-count freedom.
- Tier 4: Tier 3 + thermal-system design variables.

This gives a controlled way to study algorithm behavior as decision space
dimensionality and multimodality grow.

Background References
---------------------

- [Lithium-ion battery](https://en.wikipedia.org/wiki/Lithium-ion_battery)
- [Battery pack](https://en.wikipedia.org/wiki/Battery_pack)
- [Ohm's law](https://en.wikipedia.org/wiki/Ohm%27s_law)
- [Joule heating](https://en.wikipedia.org/wiki/Joule_heating)
- [Newton's law of cooling](https://en.wikipedia.org/wiki/Newton%27s_law_of_cooling)
- [C-rate](https://en.wikipedia.org/wiki/C_rate)
