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
- Three problem families: text, optimization, and grammar, plus a linked ideation metadata catalog.
- Lazy optional integrations for SciPy and ``trussme`` so the base install stays light.
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
   print(peanut.render_packet(include_citation=False))

That gives you the packaged problem IDs, the ideation prompt count, and a
ready-to-use text prompt packet.

Problem Families
----------------

``Text``
   Prompt packets, citations, and optional assets for human-subjects studies.

``Optimization``
   Structured numerical problems with bounds, constraints, and optional SciPy solving.

``Grammar``
   Discrete state-and-action problems for constructive design exploration.

Common Paths
------------

Choose the path that matches what you want to do next:

- Read :doc:`quickstart` to load the catalog and inspect each problem family.
- Read :doc:`problems/index` to understand the three problem types.
- Read :doc:`dependencies_and_extras` before enabling SciPy or ``trussme`` support.
- Read :doc:`examples/index` for runnable scripts you can execute immediately.
- Read :doc:`api` if you want the public surface contract first.

What Is In The Initial Catalog?
-------------------------------

- 40 ideation-focused text prompts.
- ``moneymaker_hip_pump_cost_min``: a citation-backed scalarized pump optimization benchmark.
- ``pill_capsule_min_area``: a compact nonlinear constrained optimization problem.
- ``planar_truss_span``: a discrete planar truss topology grammar with a lazy ``trussme`` adapter.

.. toctree::
   :maxdepth: 2
   :caption: Guides
   :hidden:

   quickstart
   dependencies_and_extras
   problems/index
   examples/index

.. toctree::
   :maxdepth: 2
   :caption: Reference
   :hidden:

   api
   reference/index
