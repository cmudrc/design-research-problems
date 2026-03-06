design-research-problems
========================

A compact library and compendium of canonical design research problems.

Use it to:

- load reusable human-subjects design prompts,
- run small canonical optimization benchmarks, and
- explore discrete design grammars with optional domain-specific evaluators.

Highlights
----------

- A packaged catalog of reusable design research prompts and benchmark problems.
- Five problem families: text, decision, optimization, grammar, and mcp, plus a linked ideation metadata catalog.
- A shared ``Problem`` base plus ``ComputableProblem`` layer for executable entries.
- Lazy optional integrations for SciPy, ``trussme``, ``pybamm``, and Build123d so the base install stays light.
- Problem-level feature flags plus family-level aggregated feature flags for capability discovery.
- Typed metadata and a deliberately small public API.
- Runnable examples and generated docs that stay in sync with the codebase.

Start Here
----------

If you want a five-minute start, copy this:

.. code-block:: python

   from design_research_problems import get_ideation_catalog, get_problem, list_problems

   print(list_problems())
   print(len(get_ideation_catalog().list_prompts()))
   peanut = get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
   print(peanut.render_brief(include_citation=False))

That gives you the packaged problem IDs, the ideation prompt count, and a
ready-to-use text prompt packet.

Problem Families
----------------

``Text``
   Prompt packets, citations, and optional assets for human-subjects studies.

``Decision``
   Structured decision briefs with either explicit discrete-option or empirical-choice evaluators.

``Optimization``
   Structured numerical problems with bounds, constraints, and representative built-in baselines.

``Grammar``
   Discrete state-and-action problems for constructive design exploration.

``MCP``
   Proxy-backed problems that ingest upstream MCP tool servers for agent workflows.

Common Paths
------------

Choose the path that matches what you want to do next:

- Read :doc:`quickstart` to load the catalog and inspect each problem family.
- Read :doc:`problems/index` to understand the five problem families.
- Read :doc:`problem_catalog/index` for the full generated problem-by-problem catalog.
- Read :doc:`dependencies_and_extras` before enabling SciPy, ``trussme``, ``pybamm``, or Build123d support.
- Read :doc:`examples/index` for runnable scripts you can execute immediately.
- Read :doc:`api` if you want the public surface contract first.

What Is In The Initial Catalog?
-------------------------------

- 40 ideation-focused text prompts.
- ``moneymaker_hip_pump_cost_min``: a citation-backed scalarized pump optimization benchmark.
- ``pill_capsule_min_area``: a compact nonlinear constrained optimization problem.
- ``battery_pack_18650_open_ended``: an explicit 18650 graph-netlist battery grammar with optional PyBaMM-shaped fixed-ambient single-cell surrogates and a library-owned pack solver.
- ``battery_pack_18650_series_parallel``: a constrained 18650 pack co-design grammar backed by the same optional single-cell surrogate plus the shared pack solver.
- ``planar_truss_span``, ``space_truss_span``, and six ``planar_roof_truss_*`` entries: discrete truss grammars with a lazy ``trussme`` adapter.
- ``planar_truss_span_mass_min``, ``planar_truss_span_deflection_min``, ``planar_truss_span_fos_max``, and ``space_truss_span_mass_min``: structural truss optimization benchmarks backed by the same shared ``trussme`` adapter.
- ``treadle_pump_ide_material_min``: a citation-backed scalarized treadle-pump optimization benchmark.
- ``mcp_build123d_parametric_mounting_bracket``: an MCP-ingested CAD workflow problem where agents author and evaluate Build123d scripts through a package-owned backend.

.. toctree::
   :maxdepth: 2
   :caption: Guides
   :hidden:

   quickstart
   dependencies_and_extras
   problems/index
   problem_catalog/index
   examples/index

.. toctree::
   :maxdepth: 2
   :caption: Reference
   :hidden:

   api
   reference/index
