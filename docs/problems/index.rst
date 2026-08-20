Problems
========

The five public family guides correspond one-to-one with the canonical
``ProblemKind`` values: ``text``, ``decision``, ``optimization``, ``grammar``,
and ``mcp``. “Problem kind” is the serialized taxonomy; “family” describes the
related classes and guide pages.

Family Guide
------------

.. list-table::
   :header-rows: 1

   * - Family
     - Best for
     - Recommended first stop
     - Role guidance
   * - Text
     - Prompt-based ideation and human-subjects workflows
     - :doc:`../problem_catalog/text/ideation_peanut_shelling`
     - Treat ``ideation_peanut_shelling`` as the canonical benchmark and lighter one-off briefs such as ``ideation_accessible_drinking_fountain`` as examples.
   * - Decision
     - Structured alternatives with explicit criteria
     - :doc:`../problem_catalog/decision/decision_laptop_design_profit_maximization`
     - Start with laptop design as the canonical benchmark; use the MSEval entries as smaller criterion-focused examples.
   * - Optimization
     - Objective/constraint benchmarking and solver comparisons
     - :doc:`../problem_catalog/optimization/pill_capsule_min_area`
     - Use ``planar_truss_span_mass_min`` as the canonical benchmark and ``pill_capsule_min_area`` as the lightest example.
   * - Grammar
     - Sequential constructive design behavior and transition analysis
     - :doc:`../problem_catalog/grammar/planar_truss_span`
     - Use ``planar_truss_span`` as the canonical benchmark and ``iot_home_cooling_system_design`` as a convenience demo for tool-backed state simulation.
   * - MCP
     - Tasks requiring external tool execution backends
     - :doc:`../problem_catalog/mcp/mcp_build123d_parametric_mounting_bracket`
     - The current MCP entry is both the canonical benchmark and the convenience demo for this family.

Text problems are usually the lightest path for study prototyping. Decision
problems are appropriate when options and criteria should be explicit in the
task definition. Optimization problems are appropriate when algorithmic
performance must be measured under constraints. Grammar problems are useful when
process traces and action sequences matter as much as end-state performance.
MCP-backed problems connect packaged task definitions to external computational
systems such as CAD or domain-specific services.

Family Pages
------------

.. toctree::
   :maxdepth: 1

   text
   decision
   optimization
   grammar
   mcp

Cross-Cutting Catalog Guides
----------------------------

Ideation is a curated catalog subset of the ``text`` family, while the battery
ladder spans grammar and optimization representations. Neither is an additional
``ProblemKind``.

.. toctree::
   :maxdepth: 1

   ideation
   battery_ladder

For the complete generated problem-by-problem inventory, see
:doc:`../problem_catalog/index`.

For the curated "what should I start with?" view, see :doc:`../catalog_guide`.
